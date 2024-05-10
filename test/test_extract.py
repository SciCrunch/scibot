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

    def test_mmrrc(self):
        text = """
The Lgals9 knockout (KO) mice (strain B6(FVB)-Lgals9tm1.1cfg/Mmucd) were established by Dr. Jim Paulson. The commercial source can purchase from Mutant Mouse Resource and Research Center (MMRRC). Detailed genetic information of Lgals9 KO mice can be found on the CFG functional glycomics gateway site (http://www.functionalglycomics.org/static/consortium/resources/resourcecoref.shtml) or MMRRC (Citation ID: MMRRC_031952-UCD). C57BL/6 J mice were suggested as the wild-type (WT) controls per the MMRRC recommendation. Ten-to-twelve-week-old male mice were used for the experiments. The mice were obtained and bred in Taiwan National Laboratory Animal Center and National Applied Research Laboratories (NARLabs, Taipei, Taiwan), and housed according to the Principles of Laboratory Animal Care. The procedures for animal care and handling were approved by the Animal Committee of China Medical University. There were six to eight mice per group.
"""
        found = list(find_rrids(clean_text(text)))
        print(found)
        assert len(found) == 1

    def test_find_real_data(self):
        import json
        import pathlib
        from scibot.utils import log
        from scibot.extract_new import clean_text as n_clean_text, find_rrids as n_find_rrids
        #paths = list(pathlib.Path('~/files/scibot/scibot-2023-07-05/').expanduser().glob('*.json'))
        paths = list(pathlib.Path('/tmp/scibot-json-logs-2020-09-04').glob('*.json'))
        for p in paths:
            try:
                with open(p, 'rt') as f:
                    j = json.load(f)
            except Exception as e:
                log.exception(e)
                log.error(f'error loading {p}')
                continue

            text = j['text']
            if text is None:
                log.debug(f'no text in {p}')
                continue

            found = list(find_rrids(clean_text(text)))
            n_found = list(n_find_rrids(n_clean_text(text)))
            if found != n_found:
                side_by_side = list(zip(found, n_found))
                log.debug(f'different behavior in {p}')
                breakpoint()
