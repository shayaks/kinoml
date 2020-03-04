from collections import defaultdict
from typing import List, AnyStr, Dict, Any, Callable

import pandas as pd

from .utils import KINOMEScanMapper
from ..core import BaseDatasetProvider
from ...core.protein import AminoAcidSequence
from ...core.ligand import Ligand
from ...core.measurements import PercentageDisplacementMeasurement
from ...core.conditions import AssayConditions
from ...utils import datapath, defaultdictwithargs


class PKIS2DatasetProvider(BaseDatasetProvider):

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

    __Attributes__

    - `kinases`: Dict that will generate and cache `AminoAcidSequence` objects upon access,
        with keys being any of the KINOMEScan kinase names
    - `ligands`: Dict that will generate and cache `Ligand` objects upon access, with keys
      being any of the available SMILES
    - `available_kinases`: All possible kinase names available in this dataset
    - `available_ligands`: All possible SMILES available in this dataset

    __Class attributes__

    - `_RAW_DATASHEET`: CSV file to load PKIS2 data from. If the file format is
        different (columns, etc), subclass and reimplement `self._read_dataframe`.

    __Examples__

    ```python
    >>> from kinoml.datasets.kinomescan.pkis2 import PKIS2DatasetProvider
    >>> provider = PKIS2DatasetProvider()
    >>> kin = provider.kinases["ABL2"]
    >>> lig = provider.ligands[provider.available_ligands[0]]
    >>> measurement = provider.measurements[kin, lig]
    >>> print(f"% displacement for kinase={kin.header} and ligand={lig.to_smiles()} is {measurement}"
    ```
    """

    _RAW_SPREADSHEET = datapath("kinomescan/journal.pone.0181585.s004.csv")
    _kinase_name_mapper = KINOMEScanMapper()

    ASSAY_CONDITIONS = AssayConditions(pH=7.0)

    def __init__(self, featurizers: List[Callable] = None, *args, **kwargs):
        self._df = self._read_dataframe(self._RAW_SPREADSHEET)
        self.available_kinases: List[str] = self._df.columns.tolist()
        # TODO: this might be a wrong assumption if SMILES are malformed?
        self.available_ligands: List[str] = self._df.index.tolist()

        # Lazy dicts that will only create objects on key accesss
        self.kinases: Dict[AnyStr, AminoAcidSequence] = defaultdictwithargs(
            self._process_kinase
        )
        self.ligands: Dict[AnyStr, Ligand] = defaultdictwithargs(self._process_ligand)
        self.measurements: Dict[
            AnyStr, PercentageDisplacementMeasurement
        ] = defaultdictwithargs(self._process_measurement)

        # Featurizers
        self._featurizers = featurizers

    def _read_dataframe(self, filename):
        # Kinase names are columns 7>413. Smiles appear at column 3.
        return pd.read_csv(filename, usecols=[3] + list(range(7, 413)), index_col=0)

    def _process_kinase(self, name):
        sequence = self._kinase_name_mapper.sequence_for_name(name)
        return AminoAcidSequence(sequence, header=name)

    def _process_ligand(self, ligand):
        if isinstance(ligand, str):
            return Ligand.from_smiles(ligand)
        return ligand

    def _process_measurement(self, kinase_ligand):
        assert len(kinase_ligand) == 2, "key must be (kinase, ligand)"
        kinase, ligand = kinase_ligand
        if not isinstance(kinase, AminoAcidSequence):
            raise TypeError(
                "`kinase` must be a kinoml.core.protein.AminoAcidSequence object"
            )
        if not isinstance(ligand, Ligand):
            raise TypeError("`ligand` must be a kinoml.core.ligand.Ligand object")

        smiles = ligand._provenance["smiles"]
        measurement = self._df.loc[smiles, kinase.header]
        return PercentageDisplacementMeasurement(
            measurement, conditions=self.ASSAY_CONDITIONS, components=[kinase, ligand],
        )

    def featurize(self):
        return super().featurize()
