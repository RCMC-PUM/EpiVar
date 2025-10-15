from os.path import join
from pathlib import Path

import pysam
from pybedtools import BedTool
from liftover import ChainFile
from pybedtools import Interval
from datasets.models import DataTypes


def sort_index_bgzip(file: str | Path, preset: str) -> tuple[Path, Path]:
    stem = Path(file).stem
    root = Path(file).parent

    sorted_path = Path(join(root, f"{stem}.sorted"))
    sorted_gzp_path = sorted_path.with_suffix(sorted_path.suffix + ".gz")
    index_path = sorted_gzp_path.with_suffix(sorted_gzp_path.suffix + ".tbi")

    if preset in ("bed", "gff"):
        BedTool(file).sort(header=True).saveas(sorted_path)
        BedTool(sorted_path).tabix(in_place=True, is_sorted=True, force=True)
    else:
        raise ValueError(f"Not supported file type {preset}")

    return sorted_gzp_path, index_path


def _lift_over_interval(feature: Interval, converter: ChainFile) -> str | None:
    chrom, start, end = str(feature[0]), int(feature[1]), int(feature[2])
    start = converter[chrom][start]
    end = converter[chrom][end]

    if start and end:
        new_chr_1, new_chr_2 = start[0][0], end[0][0]

        if new_chr_1 == new_chr_2:
            new_start = start[0][1]
            new_end = end[0][1]

            if new_start <= new_end:
                feature[0] = new_chr_1.replace("chr", "")
                feature[1] = new_start
                feature[2] = new_end

                return "\t".join([str(e) for e in feature])

    return None


def _lift_over_pair(feature: list, converter: "ChainFile") -> str | None:
    chrom1, start1, end1 = str(feature[0]), int(feature[1]), int(feature[2])
    chrom2, start2, end2 = str(feature[3]), int(feature[4]), int(feature[5])

    lifted_start1 = converter[chrom1][start1]
    lifted_end1 = converter[chrom1][end1]

    lifted_start2 = converter[chrom2][start2]
    lifted_end2 = converter[chrom2][end2]

    if lifted_start1 and lifted_end1 and lifted_start2 and lifted_end2:
        new_chr1 = lifted_start1[0][0]
        new_start1 = lifted_start1[0][1]
        new_end1 = lifted_end1[0][1]

        new_chr2 = lifted_start2[0][0]
        new_start2 = lifted_start2[0][1]
        new_end2 = lifted_end2[0][1]

        # Only keep if both intervals stay on the same chromosome
        if new_start1 <= new_end1 and new_start2 <= new_end2:
            feature[0] = new_chr1.replace("chr", "")
            feature[1] = new_start1
            feature[2] = new_end1
            feature[3] = new_chr2.replace("chr", "")
            feature[4] = new_start2
            feature[5] = new_end2

            return "\t".join(str(e) for e in feature)

    return None


def lift_over(
    file_in: str | Path, file_out: str | Path, chain_file_path: str | Path, data_type
) -> None:
    converter = ChainFile(chain_file_path)

    if data_type == DataTypes.bed:
        _func = _lift_over_interval
    elif data_type == DataTypes.bedpe:
        _func = _lift_over_pair
    else:
        raise ValueError(f"Unsupported file type {data_type}")

    with pysam.BGZFile(file_in, "r") as fin, pysam.BGZFile(file_out, "w") as fout:
        for raw_line in fin:
            line = raw_line.decode()  # BGZFile returns bytes, need to decode to str
            if line.startswith("#"):
                fout.write((line + "\n").encode())

            else:
                fields = line.rstrip().split("\t")
                lifted = _func(fields, converter)

                if lifted:
                    fout.write((str(lifted) + "\n").encode())


def lift_over_metrics(file_in: str | Path, file_out: str | Path) -> dict:
    total_rows = BedTool(file_in).count()
    if total_rows == 0:
        ZeroDivisionError(f"No rows in file {file_in}")

    remapped_rows = BedTool(file_out).count()

    return {
        "Total rows": total_rows,
        "Unmapped rows": total_rows - remapped_rows,
        "Unmapped fraction": round((total_rows - remapped_rows) / total_rows, 4),
        "Remapped rows": remapped_rows,
        "Remapped fraction": round(remapped_rows / total_rows, 4),
    }
