import tempfile

from django.core.files import File
from django.core.management.base import BaseCommand, CommandError
from django.core.exceptions import ObjectDoesNotExist

from reference_genomes.models import Assembly, ReferenceGenome, ChainFile
from ._private import _download_file


chain_files = [
    {
        "source": Assembly.HG19,
        "target": Assembly.HG38,
        "file": "https://hgdownload.soe.ucsc.edu/goldenPath/hg19/liftOver/hg19ToHg38.over.chain.gz",
    },
    {
        "source": Assembly.HG19,
        "target": Assembly.T2T,
        "file": "https://hgdownload.soe.ucsc.edu/goldenPath/hg19/liftOver/hg19ToHs1.over.chain.gz",
    },
    {
        "source": Assembly.HG38,
        "target": Assembly.HG19,
        "file": "https://hgdownload.soe.ucsc.edu/goldenPath/hg38/liftOver/hg38ToHg19.over.chain.gz",
    },
    {
        "source": Assembly.HG38,
        "target": Assembly.T2T,
        "file": "https://hgdownload.soe.ucsc.edu/goldenPath/hg38/liftOver/hg38ToHs1.over.chain.gz",
    },
    {
        "source": Assembly.T2T,
        "target": Assembly.HG38,
        "file": "https://hgdownload.soe.ucsc.edu/goldenPath/hs1/liftOver/hs1ToHg38.over.chain.gz",
    },
    {
        "source": Assembly.T2T,
        "target": Assembly.HG19,
        "file": "https://hgdownload.soe.ucsc.edu/goldenPath/hs1/liftOver/hs1ToHg19.over.chain.gz",
    },
]


class Command(BaseCommand):
    help = "Download liftOver chain files between supported reference assemblies"

    # ----------------------------
    # Private helpers
    # ----------------------------
    @staticmethod
    def _get_reference_genomes(record):
        """
        Resolve source/target ReferenceGenome instances for a record or
        raise a CommandError if either is missing.
        """
        try:
            source = ReferenceGenome.objects.get(name=record["source"])
            target = ReferenceGenome.objects.get(name=record["target"])
        except ObjectDoesNotExist:
            raise CommandError(
                (
                    "Either source or target reference genome for chain file "
                    f"{record['source']} → {record['target']} does not exist."
                )
            )
        return source, target

    @staticmethod
    def _get_or_create_chainfile_instance(source, target):
        """
        Return (instance, created_flag). If the chain file exists, we return it
        with created=False. Otherwise, return an unsaved instance with created=True.
        """
        try:
            instance = ChainFile.objects.get(
                source_genome=source,
                target_genome=target,
            )
            return instance, False
        except ObjectDoesNotExist:
            instance = ChainFile(
                source_genome=source,
                target_genome=target,
            )
            return instance, True

    def _download_and_attach_chain_file(self, instance: ChainFile, url: str, tmpdir: str) -> None:
        """
        Download the chain file and attach it to the given ChainFile instance,
        then save the instance.
        """
        self.stdout.write(f"Downloading: {instance} ...")
        chain_file_path = _download_file(url, save_dir=tmpdir)

        with open(chain_file_path, "rb") as fh:
            instance.file.save(chain_file_path.name, File(fh), save=False)

        instance.save()

    def handle(self, *args, **options):
        for record in chain_files:
            with tempfile.TemporaryDirectory() as tmpdir:
                source, target = self._get_reference_genomes(record)
                instance, created = self._get_or_create_chainfile_instance(source, target)

                if not created:
                    self.stdout.write(f"{instance} already exists, skipping ...")
                    continue

                self._download_and_attach_chain_file(instance, record["file"], tmpdir)
                self.stdout.write(self.style.SUCCESS(f"Imported {instance}"))

