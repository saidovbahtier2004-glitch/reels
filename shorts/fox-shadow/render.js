const {chromium}=require('playwright');const {spawn}=require('child_process');
(async()=>{const b=await chromium.launch();const p=await b.newPage({viewport:{width:1080,height:1920}});
await p.goto('file://'+process.cwd()+'/scene.html');
const dur=await p.evaluate(()=>TL.duration),fps=30,N=Math.ceil(dur*fps);
const ff=spawn('ffmpeg',['-loglevel','error','-y','-f','image2pipe','-framerate','30','-c:v','mjpeg','-i','-','-c:v','libx264','-preset','medium','-crf','18','-pix_fmt','yuv420p','video.mp4'],{stdio:['pipe','inherit','inherit']});
for(let i=0;i<N;i++){const d=await p.evaluate(t=>renderFrame(t),i/fps);
  if(!ff.stdin.write(Buffer.from(d.split(',')[1],'base64')))await new Promise(r=>ff.stdin.once('drain',r));
  if(i%200==0)console.log(i,'/',N)}
ff.stdin.end();await new Promise(r=>ff.on('close',r));await b.close()})();
