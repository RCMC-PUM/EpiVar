import pandas as pd
from typing import Literal, Type, Optional, Union, ClassVar
from pydantic import BaseModel, Field, conint, ValidationError
from django.core.exceptions import ValidationError


CHR_OPTIONS_STR = Literal[
    "1",
    "2",
    "3",
    "4",
    "5",
    "6",
    "7",
    "8",
    "9",
    "10",
    "11",
    "12",
    "13",
    "14",
    "15",
    "16",
    "17",
    "18",
    "19",
    "20",
    "21",
    "22",
    "X",
    "Y",
    "MT",
]

CHR_OPTIONS_MIXED = Literal[
    1,
    2,
    3,
    4,
    5,
    6,
    7,
    8,
    9,
    10,
    11,
    12,
    13,
    14,
    15,
    16,
    17,
    18,
    19,
    20,
    21,
    22,
    "X",
    "Y",
    "MT",
]


class BEDRecord(BaseModel):
    chrom: Union[CHR_OPTIONS_STR, CHR_OPTIONS_MIXED] = Field(alias="#chrom")
    start: conint(ge=0)
    end: conint(ge=0)
    name: str | None = Field(default=None)
    strand: Literal["+", "-", "."] | None = Field(default=None)

    expected_order: ClassVar = (
        "#chrom",
        "start",
        "end",
    )


class GeneListRecord(BaseModel):
    gene_name: str


def validate_file(filepath: str, model: Type[BaseModel], sep: str = "\t") -> None:
    # If model has required headers, validate them
    if hasattr(model, "expected_order"):
        headers = tuple(pd.read_table(filepath, sep=sep, nrows=1))
        if not headers[: len(model.expected_order)] == model.expected_order:
            raise ValidationError(
                f"Submission file should contain headers in following order: "
                f"{model.expected_order}, provided headers are: {headers}"
            )

    # Load in chunks for memory efficiency
    chunks = pd.read_table(filepath, sep=sep, chunksize=1000, dtype=str)

    for chunk_idx, chunk in enumerate(chunks, start=1):
        records = chunk.to_dict(orient="records")

        for row_idx, row in enumerate(records, start=1 + (chunk_idx - 1) * 1000):
            try:
                # Special handling for gene list files
                if model.__name__ == "GeneListRecord":
                    # GeneListRecord expects only a single column "gene_name"
                    # If file has no header, pandas will auto-generate one, so handle both cases
                    if len(row) == 1:
                        gene_val = next(iter(row.values()))
                        model(gene_name=gene_val)
                    else:
                        model(**row)
                else:
                    model(**row)

            except ValidationError as e:
                raise ValueError(
                    f"Invalid row number {row_idx} found in {filepath} --> {e}"
                )
