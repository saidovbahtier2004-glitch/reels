const {chromium}=require('playwright');const fs=require('fs');
(async()=>{const b=await chromium.launch();const p=await b.newPage({viewport:{width:1080,height:1920}});
p.on('pageerror',e=>console.log('ERR',e.message));
await p.goto('file://'+process.cwd()+'/scene.html');
for(const t of process.argv.slice(2)){const d=await p.evaluate(t=>renderFrame(+t),t);fs.writeFileSync(`/tmp/claude-0/prev/f${t}.jpg`,Buffer.from(d.split(',')[1],'base64'))}
await b.close()})();
