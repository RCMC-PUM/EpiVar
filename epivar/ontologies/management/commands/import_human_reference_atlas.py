from django.core.management.base import BaseCommand
from ontologies.models import AnatomicalStructure, CellType

from ._private import download_file, delete_temp_dir, parse_asct_table
from tqdm import tqdm


tables = [
    "https://cdn.humanatlas.io/digital-objects/asct-b/allen-brain/v1.7/assets/asct-b-allen-brain.csv",
    "https://cdn.humanatlas.io/digital-objects/asct-b/blood-pelvis/v1.4/assets/asct-b-vh-blood-pelvis.csv",
    "https://cdn.humanatlas.io/digital-objects/asct-b/blood-vasculature/v1.8/assets/asct-b-vh-blood-vasculature.csv",
    "https://cdn.humanatlas.io/digital-objects/asct-b/bone-marrow/v1.5/assets/asct-b-vh-bone-marrow.csv",
    "https://cdn.humanatlas.io/digital-objects/asct-b/eye/v1.4/assets/asct-b-vh-eye.csv",
    "https://cdn.humanatlas.io/digital-objects/asct-b/fallopian-tube/v1.4/assets/asct-b-fallopian-tube.csv",
    "https://cdn.humanatlas.io/digital-objects/asct-b/heart/v1.5/assets/asct-b-vh-heart.csv",
    "https://cdn.humanatlas.io/digital-objects/asct-b/heart/v1.5/assets/asct-b-vh-heart.csv",
    "https://cdn.humanatlas.io/digital-objects/asct-b/kidney/v1.6/assets/asct-b-vh-kidney.csv",
    "https://cdn.humanatlas.io/digital-objects/asct-b/large-intestine/v1.4/assets/asct-b-vh-large-intestine.csv",
    "https://cdn.humanatlas.io/digital-objects/asct-b/liver/v1.4/assets/asct-b-vh-liver.csv",
    "https://cdn.humanatlas.io/digital-objects/asct-b/lung/v1.5/assets/asct-b-vh-lung.csv",
    "https://cdn.humanatlas.io/digital-objects/asct-b/lymph-node/v1.4/assets/asct-b-vh-lymph-node.csv",
    "https://cdn.humanatlas.io/digital-objects/asct-b/main-bronchus/v1.3/assets/asct-b-vh-main-bronchus.csv",
    "https://cdn.humanatlas.io/digital-objects/asct-b/mouth/v1.0/assets/asct-b-vh-mouth.csv",
    "https://cdn.humanatlas.io/digital-objects/asct-b/muscular-system/v1.3/assets/asct-b-vh-muscular-system.csv",
    "https://cdn.humanatlas.io/digital-objects/asct-b/ovary/v1.3/assets/asct-b-vh-ovary.csv",
    "https://cdn.humanatlas.io/digital-objects/asct-b/palatine-tonsil/v1.1/assets/asct-b-vh-palatine-tonsil.csv",
    "https://cdn.humanatlas.io/digital-objects/asct-b/pancreas/v1.3/assets/asct-b-vh-pancreas.csv",
    "https://cdn.humanatlas.io/digital-objects/asct-b/peripheral-nervous-system/v1.2/assets/asct-b-vh-peripheral-nervous-system.csv",
    "https://cdn.humanatlas.io/digital-objects/asct-b/placenta/v1.2/assets/asct-b-vh-placenta.csv",
    "https://cdn.humanatlas.io/digital-objects/asct-b/prostate/v1.1/assets/asct-b-vh-prostate.csv",
    "https://cdn.humanatlas.io/digital-objects/asct-b/skeleton/v1.2/assets/asct-b-vh-skeleton.csv",
    "https://cdn.humanatlas.io/digital-objects/asct-b/skin/v1.5/assets/asct-b-vh-skin.csv",
    "https://cdn.humanatlas.io/digital-objects/asct-b/small-intestine/v1.2/assets/asct-b-vh-small-intestine.csv",
    "https://cdn.humanatlas.io/digital-objects/asct-b/spinal-cord/v1.1/assets/asct-b-vh-spinal-cord.csv",
    "https://cdn.humanatlas.io/digital-objects/asct-b/spinal-cord/v1.1/assets/asct-b-vh-spinal-cord.csv",
    "https://cdn.humanatlas.io/digital-objects/asct-b/spleen/v1.5/assets/asct-b-vh-spleen.csv",
    "https://cdn.humanatlas.io/digital-objects/asct-b/thymus/v1.5/assets/asct-b-vh-thymus.csv",
    "https://cdn.humanatlas.io/digital-objects/asct-b/trachea/v1.0/assets/asct-b-vh-trachea.csv",
    "https://cdn.humanatlas.io/digital-objects/asct-b/ureter/v1.0/assets/ASCT-B_VH_Ureter.csv",
    "https://cdn.humanatlas.io/digital-objects/asct-b/urinary-bladder/v1.0/assets/ASCT-B_VH_Urinary_Bladder.csv",
    "https://cdn.humanatlas.io/digital-objects/asct-b/uterus/v1.2/assets/ASCT-B_VH_Uterus.csv",
]


class Command(BaseCommand):
    help = "Import Human Reference Data (ASCT+B) tables"

    def handle(self, *args, **options):
        for table_url in tables:
            print(table_url)

            path = download_file(table_url)
            asct_table_iterator = parse_asct_table(path)

            for _, row in tqdm(asct_table_iterator, desc=table_url.split("/")[-1]):
                as_id = row.get("AS/1/ID").replace("_", ":")
                as_name = row.get("AS/1").lower()

                ct_id = row.get("CT/1/ID").replace("_", ":")
                ct_name = row.get("CT/1").lower()

                if not all([as_id, as_name, ct_id, ct_name]):
                    continue

                ans, _ = AnatomicalStructure.objects.get_or_create(
                    obo_id=as_id, defaults={"label": as_name}
                )
                clt, _ = CellType.objects.get_or_create(
                    obo_id=ct_id, defaults={"label": ct_name}
                )
                try:
                    clt.anatomical_structure.add(ans)
                except ValueError:
                    continue
            delete_temp_dir()
