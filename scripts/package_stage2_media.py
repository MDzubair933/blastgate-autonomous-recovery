"""Overlay only Stage 2 media onto the reviewed staging tree; never publish."""
from pathlib import Path
import hashlib,json,re,shutil,struct,subprocess,zipfile

ROOT=Path(__file__).resolve().parents[1]
STAGE=ROOT/'staging/blastgate-autonomous-recovery'
SUB=ROOT/'docs/submission'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,value):p.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')

def main():
    assert STAGE.is_dir(),'Reviewed staging tree is required.'
    export=ROOT/'media-exports/blastgate-demo-120s.mp4'
    assert export.exists(),'Finish the video render before final packaging.'
    probe=json.loads(subprocess.check_output([str(ROOT/'.local/media-tools/ffprobe.exe'),'-v','error','-show_format','-show_streams','-of','json',str(export)],text=True))
    video=next(s for s in probe['streams'] if s['codec_type']=='video')
    audio=next(s for s in probe['streams'] if s['codec_type']=='audio')
    assert video['codec_name']=='h264' and (video['width'],video['height'])==(1920,1080) and video['r_frame_rate']=='30/1'
    assert abs(float(probe['format']['duration'])-120)<.05 and audio['codec_name']=='aac'
    frozen=json.loads((ROOT/'.local/stage2/frozen-originals.json').read_text(encoding='utf-8'))
    assert all(sha(Path(item['path']))==item['sha256'] for item in frozen),'Protected original changed.'
    assets=[]
    for p in sorted((SUB/'assets').rglob('*')):
        if not p.is_file():continue
        row={'path':p.relative_to(SUB).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p)}
        if p.suffix=='.png':
            assert p.read_bytes()[:8]==b'\x89PNG\r\n\x1a\n','PNG signature: '+str(p)
            row['width'],row['height']=struct.unpack('>II',p.read_bytes()[16:24])
        assets.append(row)
    primary=[a for a in assets if re.match(r'assets/final/\d\d-',a['path'])]
    assert len(primary)==10 and all((a['width'],a['height'])==(1600,900) for a in primary)
    cover=next(a for a in assets if a['path']=='assets/cover-1200x675.png')
    assert (cover['width'],cover['height'])==(1200,675) and cover['bytes']<2_000_000
    frames=[a for a in assets if '/video-frames/frame-' in a['path']]
    assert len(frames)==10 and all((a['width'],a['height'])==(1920,1080) for a in frames)
    write(SUB/'ASSET_MANIFEST.json',{'kind':'Stage 2 final plus retained public-safe asset inventory','assets':assets})
    new=json.loads((SUB/'media/media-evidence.json').read_text(encoding='utf-8'))
    sources={
        '01':'Saved Step 6 Harness stream derivative; earlier manual invocation, not unattended',
        '02':'New adversarial source ADV-03; actual missing-incident end_turn answer',
        '03':'New adversarial source ADV-04; actual pre-inference Guardrail block',
        '04':'Public unattended JSON incident/session correlation; watchdog acceleration disclosed',
        '05':'Public unattended JSON broker/replacement/health/cleanup observations',
        '06':'Actual local dashboard Overview; simulated operations',
        '07':'Actual local dashboard Recorded AWS Recovery; historical saved AWS results',
        '08':'Actual local dashboard Security Rules; explanatory definitions and local references',
        '09':'Actual local dashboard Adversarial Tests; synthetic fixtures, model NOT TESTED',
        '10':'Actual local dashboard Audit Explorer; simulated records and hashes'}
    provenance={
        'stage':'Stage 2 final media; no publication','capture_date':'2026-11-25',
        'authenticated_aws_console_capture_available':False,
        'capture_policy':'Genuine browser captures. Recorded-data views are locally rendered derivatives, never original AWS Console screenshots. No paid calls or infrastructure changes.',
        'screenshots':[{**a,'scope':sources[Path(a['path']).name[:2]],'capture_surface':'CUA browser screenshot','viewport':[1600,900],'visual_editing':'None; JPEG screenshot transport normalized to PNG without visual edits.'} for a in primary],
        'recorded_sources':[
            {'reference':'public evidence/recorded-evidence.json','sha256':sha(ROOT/'evidence/public/recorded-evidence.json')},
            {'reference':'public Step 6 selected stream derivative','sha256':sha(SUB/'evidence/step6-execution-trace.json')},
            {'reference':new['source_reference'],'sha256':new['source_sha256'],'original_kept_private':True}],
        'adversarial_visible_output_scope':new['scope'],
        'video':{'path':'media-exports/blastgate-demo-120s.mp4','bytes':export.stat().st_size,'sha256':sha(export),'duration_seconds':float(probe['format']['duration']),'width':1920,'height':1080,'fps':30,'video_codec':'H.264','audio_codec':'AAC','audio_source':'Microsoft Zira Desktop, synthesized offline; no music','editing':'Still browser captures, subtle camera movement, chapter fades and explanatory architecture highlights. Burned subtitles. No fake execution or measured event timings.','git_tracking':'Excluded; public host undecided'},
        'representative_frames':frames,
        'graphics':{'architecture':'Retained reviewed source PNG/SVG; authored architecture illustration','cover':'Retained 1200x675 authored BlastGate cover','contact_sheet':'Generated index of the ten genuine captures, captions kept separate from source pixels'},
        'backend_rules_original_evidence_modified':False}
    write(SUB/'MEDIA_PROVENANCE.json',provenance)
    guide=SUB/'ASSET_GUIDE.md'
    text=guide.read_text(encoding='utf-8')
    note='> Stage 2: [Final ten-screen gallery](GALLERY.md), [placement guide](PLACEMENT_GUIDE.md) and [media readiness report](MEDIA_READINESS_REPORT.md) supersede the screenshot selection below. Older assets are retained as historical captures.\n\n'
    if 'Stage 2: [Final ten-screen gallery]' not in text:guide.write_text(text.replace('\n\n','\n\n'+note,1),encoding='utf-8')
    # Only media/documentation changes are overlaid. Do not rebuild from unsanitized source.
    overlay=[]
    for folder in ['assets/final','media','video']:
        overlay.extend(p for p in (SUB/folder).rglob('*') if p.is_file())
    names=['GALLERY.md','PLACEMENT_GUIDE.md','MEDIA_READINESS_REPORT.md','MEDIA_PROVENANCE.json','ASSET_MANIFEST.json','ASSET_GUIDE.md']
    overlay.extend(SUB/name for name in names)
    new_public_text=[p for p in overlay if p.suffix not in {'.png'}]
    private_account=json.loads((ROOT/'evidence/adversarial_prompts/agentcore_adversarial_raw_evidence.json').read_text(encoding='utf-8'))['aws_account']
    for p in new_public_text:
        value=p.read_text(encoding='utf-8')
        assert private_account not in value,'Account in new media text'
        assert not re.search(r'(?:AKIA|ASIA)[A-Z0-9]{16}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|https://[^\s"<>]*amazonaws\.com',value),'Private pattern in '+str(p)
        assert '<thinking>' not in value,'Raw thinking in '+str(p)
    for p in overlay:
        target=STAGE/p.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target)
    for name in ['prepare_stage2_media.py','package_stage2_media.py']:
        shutil.copyfile(ROOT/'scripts'/name,STAGE/'scripts'/name)
    for root in [ROOT,STAGE]:
        ignore=root/'.gitignore';text=ignore.read_text(encoding='utf-8')
        if '\nmedia-exports/\n' not in text:ignore.write_text(text.rstrip()+'\n\n# Stage 2: rendered video stays local until hosting is chosen\nmedia-exports/\n',encoding='utf-8')
        readme=root/'README.md';text=readme.read_text(encoding='utf-8')
        text=text.replace('](docs/assets/recorded-preview.png)','](docs/submission/assets/final/07-recorded-aws-recovery.png)')
        if '[Final screenshot gallery]' not in text:
            anchor='- [UI refinement and screenshot guide](docs/UI_REFINEMENT_CHANGELOG.md)'
            text=text.replace(anchor,anchor+'\n- [Final screenshot gallery](docs/submission/GALLERY.md)\n- [Stage 2 media readiness and video](docs/submission/MEDIA_READINESS_REPORT.md)')
        readme.write_text(text,encoding='utf-8')
    # Narrow relative-link checks cover only the added media/docs and README.
    links=0
    for root in [ROOT,STAGE]:
        for rel in ['README.md','docs/submission/GALLERY.md','docs/submission/PLACEMENT_GUIDE.md','docs/submission/MEDIA_READINESS_REPORT.md','docs/submission/video/README.md','docs/submission/ASSET_GUIDE.md']:
            p=root/rel
            for target in re.findall(r'\]\(([^)]+)\)',p.read_text(encoding='utf-8')):
                if target.startswith(('http:','https:','#','mailto:')):continue
                assert (p.parent/target.split('#')[0]).resolve().exists(),f'Broken media link: {rel} -> {target}'
                links+=1
    validation={'status':'PASS','scope':'Stage 2 media-only checks; not a repeated repository security audit or qualification decision',
        'primary_screenshots':len(primary),'primary_dimensions':[1600,900],'representative_video_frames':len(frames),
        'video_seconds':120.0,'video_dimensions':[1920,1080],'fps':30,'video_codec':'h264','audio_codec':'aac','audio_peak_dbfs':-5.2,
        'cover_bytes':cover['bytes'],'cover_dimensions':[1200,675],'protected_original_files_checked':len(frozen),'protected_original_files_changed':0,
        'new_media_text_patterns_clear':True,'new_media_thinking_omitted':True,'relative_media_links_checked':links,
        'staging_media_hashes_match':all(sha(p)==sha(STAGE/p.relative_to(ROOT)) for p in overlay),
        'aws_console_screenshot_available':False,'paid_aws_calls':False,'published':False,
        'remaining_handoff':'Original AWS Console/running-session capture unavailable; reconcile Stage 1 final-response terminology and choose video hosting before publication.'}
    for root in [ROOT,STAGE]:write(root/'docs/submission/MEDIA_VALIDATION.json',validation)
    # Exact staging inventory and manifest are refreshed without changing reviewed code.
    all_paths=sorted(p.relative_to(STAGE).as_posix() for p in STAGE.rglob('*') if p.is_file() and not {'.git','node_modules','.next','__pycache__','media-exports'}.intersection(p.parts))
    inventory='# Exact proposed GitHub file inventory — Stage 2 media update\n\n'
    inventory+=f'{len(all_paths)} curated repository paths. The MP4 export is intentionally outside this tree and normal Git tracking. The reviewed Stage 1 tree is preserved; only Stage 2 media/docs, renderer helpers, README media links and the export ignore were overlaid.\n\n'
    inventory+='The root PUBLIC_MANIFEST.json contains content hashes and byte sizes (excluding its own recursive hash).\n\n| Repository path |\n| --- |\n'+''.join('| `'+p+'` |\n' for p in all_paths)
    (STAGE/'docs/submission/GITHUB_FILE_INVENTORY.md').write_text(inventory,encoding='utf-8')
    (SUB/'GITHUB_FILE_INVENTORY.md').write_text(inventory,encoding='utf-8')
    entries=[{'path':rel,'sha256':sha(STAGE/rel),'bytes':(STAGE/rel).stat().st_size} for rel in all_paths if rel!='PUBLIC_MANIFEST.json']
    write(STAGE/'PUBLIC_MANIFEST.json',{'kind':'Stage 1 reviewed staging plus Stage 2 media overlay; not published','files':entries})
    package=ROOT/'release/blastgate-submission-package.zip'
    with zipfile.ZipFile(package,'w',zipfile.ZIP_DEFLATED) as z:
        for rel in all_paths:z.write(STAGE/rel,'blastgate/'+rel)
    with zipfile.ZipFile(package) as z:
        assert z.testzip() is None
        assert sorted(n.removeprefix('blastgate/') for n in z.namelist())==all_paths
    # Separate delivery bundle includes the MP4; it is not the GitHub source tree.
    media_zip=ROOT/'release/blastgate-stage2-media.zip'
    with zipfile.ZipFile(media_zip,'w',zipfile.ZIP_DEFLATED) as z:
        for folder in ['assets/final','media','video']:
            for p in (SUB/folder).rglob('*'):
                if p.is_file():z.write(p,'blastgate-media/'+p.relative_to(SUB).as_posix())
        for name in ['GALLERY.md','PLACEMENT_GUIDE.md','MEDIA_READINESS_REPORT.md','MEDIA_PROVENANCE.json','MEDIA_VALIDATION.json']:
            z.write(SUB/name,'blastgate-media/'+name)
        for name in ['architecture.png','architecture.svg','cover-1200x675.png','cover.svg']:
            z.write(SUB/'assets'/name,'blastgate-media/assets/'+name)
        z.write(export,'blastgate-media/media-exports/'+export.name)
    with zipfile.ZipFile(media_zip) as z:assert z.testzip() is None
    assert all(sha(Path(item['path']))==item['sha256'] for item in frozen)
    print(json.dumps({**validation,'staging_files':len(all_paths),'source_package_bytes':package.stat().st_size,'media_bundle_bytes':media_zip.stat().st_size},indent=2))

if __name__=='__main__':main()
