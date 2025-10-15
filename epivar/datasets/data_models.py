import pandas as pd
from typing import Literal, Type, Optional, Union, ClassVar
from pydantic import BaseModel, Field, conint, confloat, ValidationError
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


class AssociationRecord(BaseModel):
    chrom: Union[CHR_OPTIONS_STR, CHR_OPTIONS_MIXED] = Field(alias="#chrom")
    start: conint(ge=0)
    end: conint(ge=0)
    name: str
    score: Literal["."]
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
    chr: Union[CHR_OPTIONS_STR, CHR_OPTIONS_MIXED] = Field(alias="#chrom")
    start: conint(ge=0)
    end: conint(ge=0)
    name: Optional[str]
    score: Literal["."]
    strand: Literal["+", "-", "."]
    me: confloat(ge=0)
    #se: confloat(ge=0)

    expected_order: ClassVar = (
        "#chrom",
        "start",
        "end",
        "name",
        "score",
        "strand",
        "me",
        #"se",
    )


class InteractionRecord(BaseModel):
    chrom1: Union[CHR_OPTIONS_STR, CHR_OPTIONS_MIXED] = Field(alias="#chrom1")
    start1: conint(ge=0)
    end1: conint(ge=0)
    chrom2: str
    start2: conint(ge=0)
    end2: conint(ge=0)
    name: Optional[str]
    score: Literal["."]
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
