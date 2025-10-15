import os
import shutil

from django.conf import settings
from django.dispatch import receiver
from django.db.models.signals import post_save, post_delete

from datasets.tasks import update_file_checksum_task

from datasets.models import (
    AssociationData,
    InteractionData,
    ProfilingData,
    DataTypes,
)

from .models import (
    AssociationStudy,
    InteractionStudy,
    ProfilingStudy,
    IntegrationStatus,
    StudyData,
)

from reference_genomes.models import Assembly

from .tasks import (
    notify_reviewer_task,
    create_embeddings_task,
    init_integration_task,
    move_from_study_to_data_task,
    convert_bedpe_to_bed,
    adjust_pvalue_task,
    initial_test_task,
    intersection_task,
    annotate_file_task,
    sort_and_index_task,
    liftover_task,
    generate_association_study_plots,
    generate_interaction_study_plots,
    generate_profiling_study_plots,
    integration_passed,
    integration_failed,
)


@receiver(post_save, sender=StudyData)
def update_checksum(sender, instance, **kwargs):
    if instance.data:
        if instance.data.path:
            update_file_checksum_task.delay_on_commit(
                "studies",
                instance.__class__.__name__,
                instance.id,
                "data",
                "data_checksum",
            )


@receiver(post_delete, sender=StudyData)
def update_checksum(sender, instance, **kwargs):
    if instance.data:
        if instance.data.path:
            os.remove(instance.data.path)


@receiver(post_save, sender=ProfilingStudy)
@receiver(post_save, sender=InteractionStudy)
@receiver(post_save, sender=AssociationStudy)
def notify_reviewer(sender, instance, **kwargs):
    if instance.reviewer:
        notify_reviewer_task.delay_on_commit(instance.reviewer.id)


@receiver(post_save, sender=ProfilingStudy)
@receiver(post_save, sender=InteractionStudy)
@receiver(post_save, sender=AssociationStudy)
def create_embedding(sender, instance, **kwargs):
    create_embeddings_task.delay_on_commit(sender.__name__, instance.id)


@receiver(post_save, sender=AssociationStudy)
def integrate_association_data(sender, instance, **kwargs):
    if instance.integration_status != IntegrationStatus.PENDING:
        return

    # Models names passed as arguments to chained tasks
    study_model_name = sender.__name__
    data_model_name = AssociationData.__name__

    # Ordered tasks
    # Use si() instead of s() for explicit arguments passing
    workflow = (
        # Test study submitted data
        init_integration_task.si(study_model_name, instance.id)
        | initial_test_task.si(study_model_name, instance.id, "association_record")
        # Preprocess study submitted data
        | intersection_task.si(study_model_name, instance.id)
        | adjust_pvalue_task.si(study_model_name, instance.id)
        # Move study data to Data object and lift over
        | move_from_study_to_data_task.si(study_model_name, instance.id, data_model_name)
        | liftover_task.si(study_model_name, instance.id, data_model_name)
        # Sort, bgzip and index
        | sort_and_index_task.si(study_model_name, instance.id, data_model_name)
        | annotate_file_task.si(study_model_name, instance.id, data_model_name)
        | generate_association_study_plots.si(study_model_name, instance.id, data_model_name)
    )

    workflow.apply_async(
        link=integration_passed.si(sender.__name__, instance.id),
        link_error=integration_failed.si(sender.__name__, instance.id),
    )


@receiver(post_save, sender=ProfilingStudy)
def integrate_profiling_data(sender, instance, **kwargs):
    if instance.integration_status != IntegrationStatus.PENDING:
        return

    # Models names passed as arguments to chained tasks
    study_model_name = sender.__name__
    data_model_name = ProfilingData.__name__

    workflow = (
        # Test study submitted data
        init_integration_task.si(study_model_name, instance.id)
        | initial_test_task.si(study_model_name, instance.id, "profiling_record")
        # Preprocess study submitted data
        | intersection_task.si(study_model_name, instance.id)
        # Move study data to Data object and lift over
        | move_from_study_to_data_task.si(study_model_name, instance.id, data_model_name)
        | liftover_task.si(study_model_name, instance.id, data_model_name)
        # Sort, bgzip and index
        | sort_and_index_task.si(study_model_name, instance.id, data_model_name)
        | generate_profiling_study_plots.si(study_model_name, instance.id, data_model_name)
    )

    workflow.apply_async(
        link=integration_passed.si(sender.__name__, instance.id),
        link_error=integration_failed.si(sender.__name__, instance.id),
    )


@receiver(post_save, sender=InteractionStudy)
def integrate_interaction_data(sender, instance, **kwargs):
    if instance.integration_status != IntegrationStatus.PENDING:
        return

    # Models names passed as arguments to chained tasks
    study_model_name = sender.__name__
    data_model_name = InteractionData.__name__

    workflow = (
        # Test study submitted data
        init_integration_task.si(study_model_name, instance.id)
        | initial_test_task.si(study_model_name, instance.id, "interaction_record")
        # Preprocess study submitted data
        | intersection_task.si(study_model_name, instance.id)
        | convert_bedpe_to_bed.si(study_model_name, instance.id)
        | adjust_pvalue_task.si(study_model_name, instance.id)
        |
        # Move study data to Data object and lift over
        move_from_study_to_data_task.si(study_model_name, instance.id, data_model_name)
        | liftover_task.si(study_model_name, instance.id, data_model_name)
        # Sort, bgzip and index
        | sort_and_index_task.si(study_model_name, instance.id, data_model_name)
        | annotate_file_task.si(study_model_name, instance.id, data_model_name)
        | generate_interaction_study_plots.si(study_model_name, instance.id, data_model_name)
    )

    workflow.apply_async(
        link=integration_passed.si(sender.__name__, instance.id),
        link_error=integration_failed.si(sender.__name__, instance.id),
    )


@receiver(post_delete, sender=ProfilingStudy)
@receiver(post_delete, sender=InteractionStudy)
@receiver(post_delete, sender=AssociationStudy)
def delete_study(sender, instance, **kwargs):
    study_id = instance.study_id
    study_directory = os.path.join(settings.MEDIA_ROOT, "studies", study_id)

    if os.path.exists(study_directory):
        shutil.rmtree(study_directory, ignore_errors=True)


# TODO move to datasets/
@receiver(post_delete, sender=ProfilingData)
@receiver(post_delete, sender=InteractionData)
@receiver(post_delete, sender=AssociationData)
def delete_study_related_data(sender, instance, **kwargs):
    if instance.data:
        if os.path.exists(instance.data.path):
            (
                os.remove(instance.data.path)
                if os.path.exists(instance.data.path)
                else None
            )
            (
                os.remove(f"{instance.data.path}.tbi")
                if os.path.exists(f"{instance.data.path}.tbi")
                else None
            )
