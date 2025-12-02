import pandas as pd
from typing import Literal, Type, Optional, Union, ClassVar
from pydantic import BaseModel, Field, conint, confloat, ValidationError
from django.core.exceptions import ValidationError


CHR_OPTIONS_STR = Literal[
    "chr1",
    "chr2",
    "chr3",
    "chr4",
    "chr5",
    "chr6",
    "chr7",
    "chr8",
    "chr9",
    "chr10",
    "chr11",
    "chr12",
    "chr13",
    "chr14",
    "chr15",
    "chr16",
    "chr17",
    "chr18",
    "chr19",
    "chr20",
    "chr21",
    "chr22",
    "chrX",
    "chrY",
    "chrMT",
]


class AssociationRecord(BaseModel):
    chrom: CHR_OPTIONS_STR = Field(alias="#chrom")
    start: conint(ge=0)
    end: conint(ge=0)
    name: str
    strand: Literal["+", "-", "."]
    es: confloat(ge=0, le=1)
    p_value: confloat(ge=0, le=1) = Field(alias="p-value")

    expected_order: ClassVar = (
        "#chrom",
        "start",
        "end",
        "name",
        "score",
        "strand",
        "es",
        "p-value",
    )


class ProfilingRecord(BaseModel):
    chr: CHR_OPTIONS_STR = Field(alias="#chrom")
    start: conint(ge=0)
    end: conint(ge=0)
    name: Optional[str]
    strand: Literal["+", "-", "."]
    me: confloat(ge=0)
    se: confloat(ge=0)

    expected_order: ClassVar = (
        "#chrom",
        "start",
        "end",
        "name",
        "strand",
        "me",
        "se",
    )


class InteractionRecord(BaseModel):
    chrom1: CHR_OPTIONS_STR = Field(alias="#chrom1")
    start1: conint(ge=0)
    end1: conint(ge=0)
    chrom2: str
    start2: conint(ge=0)
    end2: conint(ge=0)
    name: Optional[str]
    strand1: Literal["+", "-", "."]
    strand2: Literal["+", "-", "."]
    es: confloat(ge=0, le=1)
    p_value: confloat(ge=0, le=1) = Field(alias="p-value")

    expected_order: ClassVar = (
        "#chrom1",
        "start1",
        "end1",
        "chrom2",
        "start2",
        "end2",
        "name",
        "score",
        "strand1",
        "strand2",
        "es",
        "p-value",
    )


def validate_file(filepath: str, model: Type[BaseModel], sep: str = "\t") -> None:
    if model.expected_order:
        headers = tuple(pd.read_table(filepath, sep=sep, nrows=1).columns)
        if not headers == model.expected_order:
            raise ValidationError(
                f"Submission file should contains headers in following order: {model.expected_order}, provided headers are: {headers}"
            )

    chunks = pd.read_table(filepath, sep=sep, chunksize=1000)
    for chunk in chunks:
        records = chunk.to_dict(orient="records")

        for i, row in enumerate(records, start=1):
            try:
                model(**row)
            except ValidationError as e:
                raise ValueError(f"Invalid row number {i} found in {filepath} --> {e}")
