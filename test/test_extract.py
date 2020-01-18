import unittest
from scibot.extract import clean_text, find_rrids


class TestFind(unittest.TestCase):
    def test_regex(self):
        text = """
REAGENT or RESOURCE	SOURCE	IDENTIFIER
Antibodies


anti-mouse CD3, biotin, clone 17A2	BioLegend	Cat# 100244; RRID: AB_2563947
anti-mouse CD19, biotin, clone 6D5	BioLegend	Cat# 115504; RRID: AB_312823
anti-mouse Ly-6G and Ly-6C, biotin, clone RB6-8C5	BD Biosciences	Cat# 553124; RRID: AB_394640
anti-mouse CD16/CD32, biotin, clone 2.4G2	BD Biosciences	Cat# 553143; RRID: AB_394658
anti-mouse CD11b, biotin, clone M1/70	BD Biosciences	Cat# 553309; RRID: AB_394773
Bacterial and Virus Strains


Lactobacillus plantarum (Lp 39 [IAM 12477])	ATCC	ATCC14917


Biological Samples


Healthy adult intestine tissue	Hospital Universitario de La Princesa (Madrid, Spain)	N/A
"""
        found = list(find_rrids(clean_text(text)))
        assert len(found) == 5

