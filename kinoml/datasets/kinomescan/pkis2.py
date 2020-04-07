from collections import defaultdict
from typing import List, AnyStr, Dict, Any, Callable, Union
from pathlib import Path

import pandas as pd

from .utils import KINOMEScanMapper
from .core import KinomeScanDatasetProvider
from ...core.proteins import AminoAcidSequence
from ...core.ligands import Ligand
from ...core.systems import ProteinLigandComplex
from ...core.measurements import BaseMeasurement, PercentageDisplacementMeasurement
from ...core.conditions import BaseConditions, AssayConditions
from ...features.core import BaseFeaturizer
from ...utils import datapath


class PKIS2DatasetProvider(KinomeScanDatasetProvider):

    """
    Loads PKIS2 dataset as provided in _Progress towards a public chemogenomic set
    for protein kinases and a call for contributions_[^1].

    [^1]: DOI: 10.1371/journal.pone.0181585

    It will build a dataframe where the SMILES-representation of ligands are the index
    and the columns are the kinase names. To map between KINOMEscan kinase names and
    actual sequences, helper object `kinoml.datatasets.kinomescan.utils.KINOMEScanMapper`
    is instantiated as a class attribute.

    Parameters:
        featurizers: Modify the raw chemical data into other representations.
        raw_datasheet: CSV file to load PKIS2 data from. If the file format is
            different than the default, subclass and reimplement `self._read_dataframe`.
        assay_conditions: Conditions in which the experiment took place. Default is

    __Examples__

    ```python
    >>> from kinoml.datasets.kinomescan.pkis2 import PKIS2DatasetProvider
    >>> provider = PKIS2DatasetProvider.from_source()
    >>> system = provider.systems[0]
    >>> print(f"% displacement for kinase={system.protein.name} and ligand={system.ligand.to_smiles()} is {system.measurement}"

    ```
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @classmethod
    def from_source(
        cls,
        filename: Union[AnyStr, Path] = datapath("kinomescan/journal.pone.0181585.s004.csv"),
        measurement_type: BaseMeasurement = PercentageDisplacementMeasurement,
        conditions: BaseConditions = AssayConditions(pH=7.0),
        **kwargs
    ):
        """
        Create a DatasetProvider out of the raw data in a file

        Parameters:
            filename: CSV file with the protein-ligand measurements
            measurement_type: which type of measurement was taken for each pair
            conditions: experimental conditions of the assay

        !!! todo
            Investigate lazy access and object generation
        """
        df = cls._read_dataframe(filename)

        # Read in proteins
        mapper = KINOMEScanMapper()
        kinases = []
        for kin_name in df.columns:
            sequence = mapper.sequence_for_name(kin_name)
            kinases.append(AminoAcidSequence(sequence, name=kin_name))

        # Read in ligands
        ligands = []
        for smiles in df.index[df.index.notna()]:
            ligand = Ligand.from_smiles(smiles, allow_undefined_stereo=True)
            ligands.append(ligand)

        # Build ProteinLigandComplex objects
        complexes = []
        for i, ligand in enumerate(ligands):
            for j, kinase in enumerate(kinases):
                measurement = measurement_type(
                    df.iloc[i, j], conditions=conditions, components=[kinase, ligand]
                )
                comp = ProteinLigandComplex(components=[kinase, ligand], measurement=measurement)
                complexes.append(comp)

        return cls(systems=complexes, conditions=conditions, **kwargs)

    @staticmethod
    def _read_dataframe(filename: Union[AnyStr, Path]) -> pd.DataFrame:
        """
        Consume raw datasheet into a Pandas dataframe. This method must
        provide a Dataframe with the following parameters:

        - The index must be SMILES
        - Column must be kinase names
        - Values are percentage displacement

        """
        # Kinase names are columns 7>413. Smiles appear at column 3.
        return pd.read_csv(filename, usecols=[3] + list(range(7, 413)), index_col=0)