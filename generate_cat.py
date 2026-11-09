"""Public GitHub languages -> zero to ten persistent fur patches + GIF legend."""
from pathlib import Path
from collections import Counter
from datetime import datetime, timezone
import argparse
import colorsys
import html
import json
import math
import subprocess
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
MIN_SHARE = .05
MAX_PATCHES = 10
# Body-coordinate registration is shared by the eight poses. Each slot is one
# separated organic patch, rather than a stripe or a re-coloring of the outline.
PATCH_SLOTS = [
    ('back',160,271,24,17), ('hind flank',110,310,18,23),
    ('shoulder',238,291,18,21), ('upper back',204,260,14,12),
    ('middle flank',168,317,16,13), ('lower flank',207,326,12,11),
    ('hip',113,262,13,11), ('forehead',274,201,14,12),
    ('cheek',319,266,11,10), ('chest',262,329,11,13),
]

def select_languages(repositories):
    """Compare integer counts before rounding; preserve the full denominator."""
    distinct = {repo['databaseId']:repo for repo in repositories}
    eligible = [r for r in distinct.values() if not r['isFork'] and r['primaryLanguage']]
    counts = Counter(r['primaryLanguage']['name'] for r in eligible)
    colors = {r['primaryLanguage']['name']:r['primaryLanguage']['color'] for r in eligible}
    ranked = sorted(counts,key=lambda name:(-counts[name],name.casefold()))
    all_languages = [dict(name=name,count=counts[name],share=counts[name]/len(eligible),
                          color=colors[name] or '#808090',color_fallback=colors[name] is None)
                     for name in ranked]
    # count / total >= 5 / 100, exactly; no 4.95% -> 5.0% boundary mistake.
    qualifying = [v for v in all_languages if v['count']*20 >= len(eligible)]
    selected = qualifying[:MAX_PATCHES]
    return dict(public_repositories=len(distinct),eligible_repositories=len(eligible),
                languages=all_languages,selected=selected,
                below_threshold=[v for v in all_languages if v['count']*20<len(eligible)],
                capped=qualifying[MAX_PATCHES:])

def collect(login):
    query='''query($login:String!,$cursor:String) { user(login:$login) {
      login databaseId repositories(first:100,after:$cursor,privacy:PUBLIC,ownerAffiliations:[OWNER]) {
        nodes { databaseId name url isFork primaryLanguage { name color } }
        pageInfo { hasNextPage endCursor }
      } } }'''
    repositories=[];cursor=None
    while True:
        command=['gh','api','graphql','-f','query='+query,'-f','login='+login]
        if cursor:command+=['-f','cursor='+cursor]
        result=subprocess.run(command,check=True,capture_output=True,text=True)
        response=json.loads(result.stdout)
        if response.get('errors'):raise ValueError(str(response['errors']))
        user=response['data']['user']
        if user is None:raise ValueError('GitHub account not found')
        connection=user['repositories'];repositories+=connection['nodes']
        if not connection['pageInfo']['hasNextPage']:break
        next_cursor=connection['pageInfo']['endCursor']
        if not next_cursor or next_cursor==cursor:raise ValueError('Pagination did not advance')
        cursor=next_cursor
    return dict(user=dict(login=user['login'],databaseId=user['databaseId'],repositories=dict(
        nodes=repositories,pageInfo=dict(hasNextPage=False))),
        collected_at_utc=datetime.now(timezone.utc).isoformat())

def patch_distance(x,y,slot,share):
    _,cx,cy,rx,ry=slot
    # Large language shares get slightly larger spots, but legend values remain
    # the actual repository percentages; pixel area is an illustrative cue.
    scale=min(1.10,.76+math.sqrt(share)*.50)
    dx,dy=(x-cx)/(rx*scale),(y-cy)/(ry*scale)
    angle=math.atan2(dy,dx)
    organic=1+.07*math.sin(3*angle+.6)+.04*math.cos(5*angle)
    return math.hypot(dx,dy)/organic

def apply_coat(template,selected):
    """Map selected colors onto white fur, protecting all anatomy and face details."""
    result=template.copy();data=result.load();source=template.load()
    rgb_colors=[tuple(int(v['color'].lstrip('#')[i:i+2],16) for i in (0,2,4)) for v in selected]
    visible=Counter()
    if not selected:return result,visible
    for row in range(2):
        for col in range(4):
            for y in range(182,348):
                for x in range(80,335):
                    red,green,blue,alpha=source[col*384+x,row*512+y]
                    if alpha<128:continue
                    hue,saturation,value=colorsys.rgb_to_hsv(red/255,green/255,blue/255)
                    if saturation>.20 or value<.68:continue
                    distances=[patch_distance(x,y,PATCH_SLOTS[i],v['share']) for i,v in enumerate(selected)]
                    best=min(range(len(distances)),key=distances.__getitem__)
                    if distances[best]>1:continue
                    # Leave a white channel wherever two spot boundaries approach.
                    if any(i!=best and d<1.14 for i,d in enumerate(distances)):continue
                    shade=max(.76,min(1.04,value/.97))
                    data[col*384+x,row*512+y]=tuple(min(255,round(channel*shade))
                                                    for channel in rgb_colors[best])+(alpha,)
                    visible[best]+=1
    assert result.getchannel('A').tobytes()==template.getchannel('A').tobytes()
    for i in range(len(selected)):
        assert visible[i]>200, ('Patch invisible',i,selected[i]['name'],visible[i])
    return result,visible

def hard_alpha(image):
    image=image.copy();image.putalpha(image.getchannel('A').point(lambda a:255 if a>=128 else 0))
    return image

def render_frames(sheet,world_source):
    sprites=[]
    for index in range(8):
        col,row=index%4,index//4
        tile=sheet.crop((384*col,512*row,384*(col+1),512*(row+1)))
        sprites.append(hard_alpha(tile.resize((96,128),Image.Resampling.NEAREST)))
    world=hard_alpha(world_source)
    world=world.crop(world.getchannel('A').getbbox()).resize((140,140),Image.Resampling.NEAREST)
    mask=Image.new('L',(140,140));ImageDraw.Draw(mask).ellipse((3,3,136,136),fill=255)
    frames=[]
    for index in range(80):
        frame=Image.new('RGBA',(256,240))
        globe=world.copy();surface=world.rotate(index*360/80,Image.Resampling.NEAREST)
        interior=Image.composite(surface.getchannel('A'),Image.new('L',(140,140)),mask)
        globe.paste(surface,(0,0),interior)
        frame.alpha_composite(globe,(58,90));frame.alpha_composite(sprites[index%8],(80,-6))
        frames.append(frame.resize((512,480),Image.Resampling.NEAREST))
    return frames

def font(size,bold=False):
    paths=[Path('C:/Windows/Fonts')/('segoeuib.ttf' if bold else 'segoeui.ttf'),
           Path('/usr/share/fonts/truetype/dejavu')/('DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf')]
    for path in paths:
        if path.exists():return ImageFont.truetype(str(path),size)
    return ImageFont.load_default(size=size)

def legend_panel(login,selected):
    columns=2;rows=math.ceil(len(selected)/columns)
    height=72+max(1,rows)*36
    panel=Image.new('RGBA',(512,height));draw=ImageDraw.Draw(panel)
    draw.rounded_rectangle((8,4,503,height-5),radius=12,fill='#f8fafc',outline='#c9d1dc',width=1)
    draw.text((24,16),f'{login} · languages',font=font(17,True),fill='#20293a')
    if not selected:
        draw.text((24,54),'No languages at or above 5% · white cat',font=font(15),fill='#465367')
    for index,language in enumerate(selected):
        x=24+(index%columns)*246;y=53+(index//columns)*36
        draw.rounded_rectangle((x,y+2,x+17,y+19),radius=3,fill=language['color'],outline='#667080')
        label=f"{language['name']} {language['share']:.1%}"
        draw.text((x+26,y-1),label,font=font(16),fill='#20293a')
    if selected:
        draw.text((24,height-30),'Public repo share · minimum 5% · up to 10 patches',font=font(12),fill='#586579')
    return panel

def attach_legend(frames,panel):
    result=[]
    for frame in frames:
        combined=Image.new('RGBA',(512,480+panel.height))
        combined.alpha_composite(frame);combined.alpha_composite(panel,(0,480));result.append(combined)
    return result

def save_gif(path,frames,selected):
    # Reserve the exact language colors in the global palette, ensuring swatches
    # and representative patch colors remain consistent after GIF quantization.
    strip=Image.new('RGB',(512*8,frames[0].height),'#151b2a')
    for index in range(8):strip.paste(frames[index*10].convert('RGB'),(index*512,0))
    adaptive=strip.quantize(colors=96,method=Image.Quantize.MEDIANCUT).getpalette()[:96*3]
    exact=[]
    for v in selected:exact += [int(v['color'].lstrip('#')[i:i+2],16) for i in (0,2,4)]
    palette_bytes=exact+adaptive
    palette_bytes+=(palette_bytes[:3] or [0,0,0])*((768-len(palette_bytes))//3)
    palette=Image.new('P',(1,1));palette.putpalette(palette_bytes[:768])
    output_palette=([0,0,0]+palette_bytes)[:768]
    encoded=[]
    for frame in frames:
        quantized=frame.convert('RGB').quantize(palette=palette,dither=Image.Dither.NONE)
        result=Image.new('P',frame.size);result.putpalette(output_palette)
        result.putdata([int(v)+1 if a else 0 for v,a in zip(quantized.get_flattened_data(),frame.getchannel('A').get_flattened_data())])
        encoded.append(result)
    encoded[0].save(path,save_all=True,append_images=encoded[1:],duration=80,
                    loop=0,transparency=0,disposal=2,optimize=True)
    gif=Image.open(path);assert gif.n_frames==80 and gif.info['loop']==0
    duration=0
    for index in range(gif.n_frames):
        gif.seek(index);duration+=gif.info['duration']
        assert gif.convert('RGBA').getchannel('A').getextrema()[0]==0
    assert duration==6400

def build(snapshot,output_dir=None):
    output_dir=Path(output_dir) if output_dir is not None else ROOT/'generated'
    output_dir.mkdir(parents=True,exist_ok=True)
    user=snapshot['user'];login=user['login']
    assert not user['repositories']['pageInfo']['hasNextPage'], 'Incomplete snapshot'
    statistics=select_languages(user['repositories']['nodes']);selected=statistics['selected']
    template=Image.open(ROOT/'assets'/'white-cat-template.png').convert('RGBA')
    assert template.size==(1536,1024)
    sheet,visible=apply_coat(template,selected)
    sheet.save(output_dir/'personalized-sheet.png')
    frames=render_frames(sheet,Image.open(ROOT/'assets'/'globe-template.png').convert('RGBA'))
    panel=legend_panel(login,selected);combined=attach_legend(frames,panel)
    filename=login+'-cat-with-legend.gif'
    save_gif(output_dir/filename,combined,selected)
    save_gif(output_dir/(login+'-cat-globe.gif'),frames,selected)
    combined[0].save(output_dir/'cat-with-legend-still.png');panel.save(output_dir/'language-legend.png')
    summary=dict(login=login,collected_at_utc=snapshot.get('collected_at_utc'),
                 method='Primary-language counts over all owned public non-fork repositories with a primary language.',
                 minimum_share=MIN_SHARE,maximum_patches=MAX_PATCHES,
                 percentage_rule='Original denominator; never renormalized after filtering or limiting.',
                 patch_area_rule='Patch sizes are illustrative; exact shares are shown in the legend.',
                 patch_count=len(selected),patch_pixels={selected[i]['name']:count for i,count in visible.items()},
                 **statistics)
    (output_dir/'personalization.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    colors=''.join(f"<li><span style='background:{v['color']}'></span>{html.escape(v['name'])} — {v['share']:.1%} <code>{v['color']}</code></li>" for v in selected)
    if not selected:colors='<li>No languages qualify; the cat has zero patches.</li>'
    (output_dir/'preview.html').write_text(f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(login)}'s language cat</title><style>body{{margin:0;font:16px/1.6 system-ui,sans-serif;background:#f3f5f8;color:#253047}}header,footer{{padding:24px}}h1{{font-size:28px;margin:0}}main{{display:flex;flex-wrap:wrap}}section{{flex:1;padding:20px;min-width:min(100%,512px)}}.light{{background:white;color:#1f2328}}.dark{{background:#0d1117;color:#f0f6fc}}img{{display:block;max-width:100%;height:auto}}a{{color:inherit}}li span{{display:inline-block;width:16px;height:16px;margin-right:12px;border:1px solid #697080;border-radius:3px}}li{{margin:8px 0}}code{{font-size:12px}}</style></head><body><header><h1>{html.escape(login)}'s cat · {len(selected)} patches</h1><p>Languages ≥5% · maximum 10 · repository-count percentages</p><p><a href="{filename}" download>Download GIF with legend</a> · <a href="{login}-cat-globe.gif" download>Download cat only</a></p></header><main><section class="light"><h2>Light</h2><img src="{filename}" width="512" alt="Pixel cat on a globe with language colors and percentages"></section><section class="dark"><h2>Dark</h2><img src="{filename}" width="512" alt="Same animated cat and legend on a dark background"></section></main><footer><h2>Color key</h2><ul>{colors}</ul><p>Shares use all {statistics['eligible_repositories']} eligible repositories before filtering. Smaller languages do not become part of another language's percentage.</p><p>Missing data collection fails; a confirmed empty account or no qualifying languages produces the white cat. Larger shares get slightly larger spots; patch area is not an exact percentage chart.</p></footer></body></html>''',encoding='utf-8')
    return summary

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--login',default='ammar31mawassi')
    parser.add_argument('--refresh',action='store_true');parser.add_argument('--snapshot',type=Path)
    parser.add_argument('--output-dir',type=Path,default=ROOT/'generated')
    args=parser.parse_args()
    args.output_dir.mkdir(parents=True,exist_ok=True)
    args.snapshot=args.snapshot or args.output_dir/'github-snapshot.json'
    if args.refresh:
        snapshot=collect(args.login);args.snapshot.write_text(json.dumps(snapshot,indent=2),encoding='utf-8')
    else:snapshot=json.loads(args.snapshot.read_text(encoding='utf-8'))
    if snapshot['user']['login'].casefold()!=args.login.casefold():raise ValueError('Snapshot account differs from requested login')
    summary=build(snapshot,args.output_dir)
    print(json.dumps(dict(login=summary['login'],patch_count=summary['patch_count'],selected=summary['selected']),indent=2))

if __name__=='__main__':main()
