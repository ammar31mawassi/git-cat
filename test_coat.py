"""Meaningful boundary checks for eligibility and the rendered patch masks."""
import unittest
from PIL import Image
from generate_cat import ROOT, select_languages, apply_coat

def repositories(counts):
    result=[]
    for name,count in counts.items():
        for _ in range(count):
            result.append(dict(databaseId=len(result)+1,isFork=False,
                               primaryLanguage=dict(name=name,color='#e34c26')))
    return result

class LanguageRules(unittest.TestCase):
    def test_five_percent_is_included_below_five_excluded(self):
        # Exactly 5/100 qualifies; 4/100 does not. Denominator stays 100.
        result=select_languages(repositories({'Main':91,'Boundary':5,'Small':4}))
        self.assertEqual([v['name'] for v in result['selected']],['Main','Boundary'])
        self.assertEqual(result['selected'][1]['share'],.05)
        self.assertEqual(result['selected'][0]['share'],.91)

    def test_rounding_cannot_promote_a_language(self):
        result=select_languages(repositories({'Main':192,'Almost':10}))
        self.assertEqual(f"{10/202:.1%}",'5.0%')
        self.assertEqual([v['name'] for v in result['selected']],['Main'])

    def test_cap_and_stable_ties(self):
        result=select_languages(repositories({f'Language {i:02}':1 for i in range(12)}))
        self.assertEqual(len(result['selected']),10)
        self.assertEqual(len(result['capped']),2)
        self.assertEqual(result['selected'][0]['name'],'Language 00')
        self.assertEqual(result['selected'][-1]['name'],'Language 09')
        self.assertAlmostEqual(result['selected'][0]['share'],1/12)

    def test_empty_and_all_below_threshold(self):
        self.assertEqual(select_languages([])['selected'],[])
        result=select_languages(repositories({f'Language {i}':1 for i in range(21)}))
        self.assertEqual(result['selected'],[])

    def test_forks_unknown_languages_and_duplicates_do_not_inflate_shares(self):
        good=repositories({'Python':1})
        result=select_languages(good+good+[dict(databaseId=2,isFork=True,
               primaryLanguage=dict(name='Java',color='#b07219')),
               dict(databaseId=3,isFork=False,primaryLanguage=None)])
        self.assertEqual(result['eligible_repositories'],1)
        self.assertEqual(result['selected'][0]['share'],1)

    def test_zero_patches_preserves_exact_white_template(self):
        template=Image.open(ROOT/'assets'/'white-cat-template.png').convert('RGBA')
        white,counts=apply_coat(template,[])
        self.assertEqual(white.tobytes(),template.tobytes())
        self.assertFalse(counts)

    def test_every_slot_is_visible_in_all_eight_poses(self):
        template=Image.open(ROOT/'assets'/'white-cat-template.png').convert('RGBA')
        # Use one unique color per patch and an unshaded test palette.
        selected=[dict(name=f'Test {i}',share=.10,color=color) for i,color in enumerate(
            ['#f34b7d','#3572a5','#b07219','#f1e05a','#3178c6',
             '#6e4c13','#555555','#e34c26','#563d7c','#00add8'])]
        coat,counts=apply_coat(template,selected)
        self.assertEqual(len(counts),10)
        self.assertEqual(coat.getchannel('A').tobytes(),template.getchannel('A').tobytes())
        for pose in range(8):
            x,y=pose%4*384,pose//4*512
            crop=coat.crop((x,y,x+384,y+512))
            original=template.crop((x,y,x+384,y+512))
            changed=[v for v,o in zip(crop.get_flattened_data(),original.get_flattened_data()) if v!=o]
            for color in selected:
                rgb=tuple(int(color['color'][i:i+2],16) for i in (1,3,5))
                # Shading scales all three channels uniformly.
                def belongs(pixel):
                    ratios=[pixel[i]/rgb[i] for i in range(3) if rgb[i]]
                    return max(ratios)-min(ratios)<.04 and min(ratios)>.72
                self.assertGreater(sum(belongs(v) for v in changed),20,(pose,color['name']))

if __name__=='__main__':unittest.main()
