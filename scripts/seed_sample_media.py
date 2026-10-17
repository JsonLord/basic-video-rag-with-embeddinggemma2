"""Generate deterministic synthetic teaching slides/video without external assets."""
from pathlib import Path
import subprocess
from PIL import Image,ImageDraw,ImageFont
root=Path(__file__).resolve().parent.parent/'web/public/sample';root.mkdir(parents=True,exist_ok=True)
font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',22)
small=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',14)
for n,title in enumerate(['PREPARE THE WORKBENCH','CAMERA & LIGHTING','EVIDENCE IN VIDEO'],1):
    image=Image.new('RGB',(640,360),'#10171e');d=ImageDraw.Draw(image)
    d.rectangle((0,0,640,5),fill=['#3987e5','#199e70','#d95926'][n-1]);d.text((28,28),'VISUAL MENTOR / SAMPLE '+str(n),fill='#8eabbf',font=small)
    d.text((28,65),title,fill='#f0f5fa',font=font)
    if n==1:
        d.rounded_rectangle((65,155,575,285),12,fill='#253443',outline='#3987e5',width=2)
        for x in [100,260,420]:
            d.rounded_rectangle((x,180,x+110,250),8,fill='#14232f',outline='#5b87ac',width=2)
        for x,label in [(112,'CLEAR'),(272,'CHECK'),(432,'START')]:d.text((x,205),label,fill='#c5d6e4',font=small)
    elif n==2:
        d.ellipse((62,155,162,255),outline='#d1aa44',width=4);d.line((160,205,240,205),fill='#d1aa44',width=3)
        d.rounded_rectangle((248,130,565,290),8,fill='#1b3040',outline='#199e70',width=3)
        d.ellipse((378,160,428,210),outline='#a3d6c3',width=3);d.arc((338,210,468,310),180,360,fill='#a3d6c3',width=3)
    else:
        for i in range(4):
            x=30+150*i;d.rounded_rectangle((x,145,x+130,245),8,fill='#22313d',outline='#d95926' if i==1 else '#526473',width=2);d.text((x+15,185),f'00:{i*15:02d}',fill='#f1d5c2',font=small)
        d.line((30,275,610,275),fill='#d95926',width=3);d.ellipse((175,268,189,282),fill='#f1d5c2')
    d.text((28,325),'Synthetic evaluation footage - no live inference',fill='#8eabbf',font=small)
    path=root/f'thumb-{n}.jpg';image.save(path,quality=90)
# All sample entries refer to this clearly synthetic two-stage clip; fixture transcripts
# describe its educational context, not live provider observations.
subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-loop','1','-i',str(root/'thumb-1.jpg'),'-loop','1','-i',str(root/'thumb-2.jpg'),'-filter_complex','[0:v]trim=duration=30,setpts=PTS-STARTPTS[a];[1:v]trim=duration=30,setpts=PTS-STARTPTS[b];[a][b]concat=n=2:v=1:a=0[out]','-map','[out]','-r','5','-t','60','-c:v','libx264','-threads','1','-preset','veryfast','-pix_fmt','yuv420p','-movflags','+faststart','-y',str(root/'video.mp4')],check=True)
