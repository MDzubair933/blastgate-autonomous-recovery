param(
  [string]$Ffmpeg,
  [string]$Ffprobe,
  [switch]$ImagesOnly,
  [switch]$SkipSpeech,
  [switch]$Resume
)
$ErrorActionPreference='Stop'
Add-Type -AssemblyName System.Drawing
$ProjectRoot=(Resolve-Path (Join-Path $PSScriptRoot '../../..')).Path
$AssetRoot=Join-Path $PSScriptRoot '../assets'
$FinalRoot=Join-Path $AssetRoot 'final'
$WorkRoot=Join-Path $ProjectRoot '.local/stage2/video-work'
$ExportRoot=Join-Path $ProjectRoot 'media-exports'
New-Item -ItemType Directory -Force -Path $WorkRoot,$ExportRoot,(Join-Path $FinalRoot 'video-frames') | Out-Null
if(!$Ffmpeg){$Ffmpeg=Join-Path $ProjectRoot '.local/media-tools/ffmpeg.exe'}
if(!$Ffprobe){$Ffprobe=Join-Path $ProjectRoot '.local/media-tools/ffprobe.exe'}
$Plan=Get-Content -LiteralPath (Join-Path $PSScriptRoot 'project.json') -Raw | ConvertFrom-Json
$Dark=[System.Drawing.ColorTranslator]::FromHtml('#0b0f14')
$White=[System.Drawing.ColorTranslator]::FromHtml('#f5f4f1')
$Muted=[System.Drawing.ColorTranslator]::FromHtml('#b5b8bd')
$Gold=[System.Drawing.ColorTranslator]::FromHtml('#d8a955')
function Brush($Color){[System.Drawing.SolidBrush]::new($Color)}
function Font($Size,$Family='Segoe UI',$Style=[System.Drawing.FontStyle]::Regular){[System.Drawing.Font]::new($Family,[single]$Size,$Style,[System.Drawing.GraphicsUnit]::Pixel)}
function Text($Graphics,$Text,$X,$Y,$Width,$Height,$Size,$Color,$Family='Segoe UI'){
 $f=Font $Size $Family;$b=Brush $Color
 $Graphics.DrawString($Text,$f,$b,[System.Drawing.RectangleF]::new($X,$Y,$Width,$Height))
 $f.Dispose();$b.Dispose()
}
function Canvas($Width,$Height){
 $bmp=[System.Drawing.Bitmap]::new($Width,$Height)
 $g=[System.Drawing.Graphics]::FromImage($bmp)
 $g.Clear($Dark);$g.SmoothingMode='AntiAlias';$g.TextRenderingHint='AntiAliasGridFit';$g.InterpolationMode='HighQualityBicubic'
 return @{Bitmap=$bmp;Graphics=$g}
}
function FitImage($Graphics,$Path,$X,$Y,$Width,$Height){
 $im=[System.Drawing.Image]::FromFile($Path)
 $scale=[Math]::Min($Width/$im.Width,$Height/$im.Height)
 $w=[int]($im.Width*$scale);$h=[int]($im.Height*$scale)
 $Graphics.DrawImage($im,[System.Drawing.Rectangle]::new([int]($X+($Width-$w)/2),[int]($Y+($Height-$h)/2),$w,$h))
 $im.Dispose()
}
# CUA screenshot transport may return JPEG bytes; normalize the container only, without visual edits.
foreach($p in Get-ChildItem -LiteralPath $FinalRoot -Filter '*.png' -File){
 $bytes=[System.IO.File]::ReadAllBytes($p.FullName)
 if($bytes[0] -ne 137){
  $im=[System.Drawing.Image]::FromFile($p.FullName);$temp=$p.FullName+'.normalize.png'
  $im.Save($temp,[System.Drawing.Imaging.ImageFormat]::Png);$im.Dispose()
  Move-Item -LiteralPath $temp -Destination $p.FullName -Force
 }
}
$Titles=@('AgentCore saved execution','Actual adversarial agent answer','Actual Guardrail block','Dispatcher session observation','Distinct healthy ECS replacement','Overview · simulated','Recorded AWS recovery','R1–R8 · explanatory dashboard','Adversarial tests · local fixtures','Audit Explorer · simulated')
$Screens=@(Get-ChildItem -LiteralPath $FinalRoot -Filter '*.png' -File | Where-Object {$_.Name -match '^\d\d-'} | Sort-Object Name)
if($Screens.Count -ne 10){throw 'Expected exactly ten numbered captures.'}
$sheet=Canvas 2000 3130
Text $sheet.Graphics 'BLASTGATE / FINAL EVIDENCE GALLERY' 60 34 1850 50 34 $White
Text $sheet.Graphics 'Recorded AWS Execution views and simulated dashboards are labeled separately. No AWS Console recreation.' 60 90 1850 46 21 $Muted
for($i=0;$i -lt $Screens.Count;$i++){
 $x=50+($i%2)*980;$y=160+[Math]::Floor($i/2)*588
 FitImage $sheet.Graphics $Screens[$i].FullName $x $y 940 529
 Text $sheet.Graphics ('{0:00}  {1}' -f ($i+1),$Titles[$i]) $x ($y+537) 940 43 23 $White
}
$sheet.Bitmap.Save((Join-Path $FinalRoot 'contact-sheet.png'),[System.Drawing.Imaging.ImageFormat]::Png)
$sheet.Graphics.Dispose();$sheet.Bitmap.Dispose()
foreach($s in $Plan.scenes){
 $c=Canvas 1920 1080
 if($s.asset -eq 'cover'){
  FitImage $c.Graphics (Join-Path $AssetRoot 'cover-1200x675.png') 0 0 1920 1080
 }else{
  Text $c.Graphics 'BLASTGATE' 64 27 400 35 22 $Gold
  Text $c.Graphics $s.title 64 70 1790 62 42 $White 'Georgia'
  Text $c.Graphics $s.scope 66 137 1780 35 20 $Muted
  $image=if($s.asset -eq 'architecture'){Join-Path $AssetRoot 'architecture.png'}else{Join-Path $FinalRoot ($s.asset+'.png')}
  FitImage $c.Graphics $image 130 183 1660 780
  if($s.asset -eq 'architecture'){
   Text $c.Graphics 'EXPLANATORY ANIMATION — NO MEASURED EVENT TIMINGS' 66 964 1780 28 18 $Muted
  }
 }
 $c.Bitmap.Save((Join-Path $WorkRoot ($s.id+'.png')),[System.Drawing.Imaging.ImageFormat]::Png)
 $c.Graphics.Dispose();$c.Bitmap.Dispose()
}
Write-Output 'Prepared contact sheet and eleven editable scene compositions.'
if($ImagesOnly){exit 0}
if(!(Test-Path -LiteralPath $Ffmpeg)){throw 'Supply the path to an existing FFmpeg executable.'}
if(!$SkipSpeech){
 Add-Type -AssemblyName System.Speech
 $speaker=[System.Speech.Synthesis.SpeechSynthesizer]::new()
 $speaker.SelectVoice('Microsoft Zira Desktop');$speaker.Rate=0;$speaker.Volume=100
}
$clips=@();$audioReport=@()
foreach($s in $Plan.scenes){
 $wav=Join-Path $WorkRoot ($s.id+'.wav')
 if(!$SkipSpeech){$speaker.SetOutputToWaveFile($wav);$speaker.Speak($s.narration);$speaker.SetOutputToNull()}
 $audioDuration=[double](& $Ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 $wav)
 $tempo=[Math]::Max(1.0,$audioDuration/($s.duration-0.8))
 if($tempo -gt 1.3){throw ('Narration too long for scene '+$s.id)}
 $audioReport+=@{scene=$s.id;spoken_seconds=$audioDuration;slot_seconds=$s.duration;tempo=$tempo}
 $fadeStart=$s.duration-0.35
 $vf="scale=1920:1080,zoompan=z='min(zoom+0.000025,1.008)':x='(iw-iw/zoom)/2':y='(ih-ih/zoom)/2':d=1:s=1920x1080:fps=30,fade=t=in:st=0:d=0.35,fade=t=out:st=${fadeStart}:d=0.35"
 # Source diagram at scale .78, centered at x336/y183. Highlights explain component order only.
 if($s.id -eq 'architecture-detect'){
  for($j=0;$j -lt 4;$j++){
   $x=336+[int]((60+$j*390)*0.78);$y=183+[int](220*0.78);$a=$j*3;$b=($j+1)*3
   $vf+=",drawbox=x=${x}:y=${y}:w=234:h=116:color=0xD8A955@0.85:t=3:enable='between(t,${a},${b})'"
  }
 }
 if($s.id -eq 'architecture-authority'){
  $j=0
  foreach($sourceX in @(1230,840,450,60)){
   $x=336+[int]($sourceX*0.78);$y=183+[int](460*0.78);$a=$j*3.25;$b=($j+1)*3.25
   $vf+=",drawbox=x=${x}:y=${y}:w=234:h=116:color=0x70C9BE@0.85:t=3:enable='between(t,${a},${b})'";$j++
  }
 }
 $clip=Join-Path $WorkRoot ($s.id+'.mp4')
 if($Resume -and (Test-Path -LiteralPath $clip)){$clips+=$clip;Write-Output ('Reused completed '+$s.id);continue}
 & $Ffmpeg -hide_banner -loglevel error -y -loop 1 -framerate 30 -i (Join-Path $WorkRoot ($s.id+'.png')) -i $wav -vf $vf -af "atempo=$tempo,apad,atrim=0:$($s.duration),afade=t=in:st=0:d=0.05,afade=t=out:st=$fadeStart`:d=0.2" -t $s.duration -r 30 -c:v libx264 -preset veryfast -crf 18 -pix_fmt yuv420p -threads 4 -c:a aac -b:a 160k -ar 48000 -ac 2 $clip
 if($LASTEXITCODE -ne 0){throw ('FFmpeg failed for '+$s.id)}
 $clips+=$clip
 Write-Output ('Rendered '+$s.id+' ('+$s.duration+'s)')
}
if(!$SkipSpeech){$speaker.Dispose()}
$audioReport | ConvertTo-Json -Depth 5 | Set-Content (Join-Path $WorkRoot 'narration-timing.json') -Encoding utf8
$concat=Join-Path $WorkRoot 'clips.txt'
($clips | ForEach-Object { "file '"+$_.Replace('\','/')+"'" }) | Set-Content -LiteralPath $concat -Encoding utf8NoBOM
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'subtitles.srt') -Destination (Join-Path $WorkRoot 'subtitles.srt') -Force
$output=Join-Path $ExportRoot 'blastgate-demo-120s.mp4'
Push-Location $WorkRoot
try{
 & $Ffmpeg -hide_banner -loglevel error -y -f concat -safe 0 -i $concat -vf "subtitles=subtitles.srt:force_style='Fontname=Segoe UI,Fontsize=12,PrimaryColour=&H00F1F4F5,OutlineColour=&H00140F0B,BorderStyle=3,Outline=1,Shadow=0,MarginV=10'" -t 120 -r 30 -c:v libx264 -preset fast -crf 19 -pix_fmt yuv420p -threads 4 -c:a aac -b:a 160k -movflags +faststart -metadata title='BlastGate — Autonomous Recovery. Provable Boundaries.' -metadata comment='Edited technical demo. Archived observations labeled Recorded AWS Execution; architecture animation is explanatory.' $output
 if($LASTEXITCODE -ne 0){throw 'Final MP4 render failed.'}
}finally{Pop-Location}
$probe=& $Ffprobe -v error -show_format -show_streams -of json $output
$probe | Set-Content (Join-Path $WorkRoot 'ffprobe.json') -Encoding utf8
foreach($t in @(4,20,34,46,59,72,86,98,109,116)){
 & $Ffmpeg -hide_banner -loglevel error -y -ss $t -i $output -frames:v 1 (Join-Path $FinalRoot ('video-frames/frame-{0:000}s.png' -f $t))
 if($LASTEXITCODE -ne 0){throw 'Representative frame export failed.'}
}
$frameSheet=Canvas 2000 3020
Text $frameSheet.Graphics 'BLASTGATE / DECODED VIDEO FRAME REVIEW' 50 32 1850 50 32 $White
$frameFiles=@(Get-ChildItem -LiteralPath (Join-Path $FinalRoot 'video-frames') -Filter 'frame-*.png' | Sort-Object Name)
for($i=0;$i -lt $frameFiles.Count;$i++){
 $x=50+($i%2)*980;$y=110+[Math]::Floor($i/2)*575
 FitImage $frameSheet.Graphics $frameFiles[$i].FullName $x $y 940 529
 Text $frameSheet.Graphics $frameFiles[$i].Name $x ($y+535) 940 35 22 $White
}
$frameSheet.Bitmap.Save((Join-Path $FinalRoot 'video-frames/contact-sheet.png'),[System.Drawing.Imaging.ImageFormat]::Png)
$frameSheet.Graphics.Dispose();$frameSheet.Bitmap.Dispose()
Write-Output ('Completed '+$output)
