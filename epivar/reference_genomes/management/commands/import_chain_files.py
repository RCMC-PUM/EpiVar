import sys

from django.core.files import File
from django.core.management.base import BaseCommand
from django.core.exceptions import ObjectDoesNotExist

from reference_genomes.models import Assembly, ReferenceGenome, ChainFile
from ._private import download_file, delete_temp_dir

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
    help = "Download chain files"

    def handle(self, *args, **options):
        for record in chain_files:
            try:
                source = ReferenceGenome.objects.get(name=record["source"])
                target = ReferenceGenome.objects.get(name=record["target"])
            except ObjectDoesNotExist:
                print(
                    f"Either source or target reference genome for specified chain file does not exists."
                )
                sys.exit(-1)

            try:
                instance = ChainFile.objects.get(
                    source_genome=source, target_genome=target
                )
                print(f"{instance} already exists, skipping ...")

            except ObjectDoesNotExist:
                instance = ChainFile(source_genome=source, target_genome=target)

                chain_file_path = download_file(record["file"])
                with open(chain_file_path, "rb") as chain_file:
                    instance.file.save(
                        chain_file_path.name, File(chain_file), save=False
                    )
                    instance.save()

        delete_temp_dir()
