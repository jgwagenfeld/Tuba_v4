// Geometry-only WebGL regression. These colored surfaces are rendering test
// fixtures, not solver results. Run: node scripts/rendering-smoke.mjs
import assert from "node:assert/strict";
import { mkdirSync, realpathSync, writeFileSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { createServer } from "vite";
import { chromium } from "@playwright/test";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
const output = resolve(root,".build/rendering-review");
mkdirSync(output,{recursive:true});
const html = `<!doctype html><html><head><title>Tuba rendering diagnostics</title>
<style>body{font:16px system-ui;background:#f8fafc;margin:20px}canvas{width:640px;height:520px;display:block}button{margin:8px 8px 8px 0;padding:8px}p{max-width:640px}</style></head>
<body><h1>Profile and transparency diagnostics</h1><p>Geometry fixtures only. No engineering or solver results.</p>
<button id="overlap">Intersecting translucent surfaces</button><button id="profile">Square profile</button><button id="camera">Focused camera</button>
<div style="position:relative;width:max-content"><canvas id="canvas" width="640" height="520"></canvas><aside id="inspector" hidden style="position:absolute;right:0;top:0;height:100%;width:240px;background:#17242b">Inspector overlay</aside></div><p>Drag to orbit. The square member should keep flat faces. Overlapping translucent surfaces should keep stable colors.</p>
<script type="module">
import {createThreeCanvasRenderer,getViewportInsets} from '/viewer/src/renderer.js';
const canvas=document.querySelector('canvas');
const inspector=document.querySelector('#inspector');
const renderer=createThreeCanvasRenderer(canvas,{viewportInsets:()=>getViewportInsets(canvas,{right:inspector}),resizeTargets:[inspector]});
const plane=(id,z,color,opacity=1)=>({id,format:'mesh',object_ids:[id],bounds:[-1,-1,-1,1,1,1],
 generation_config:{vertices:[[-1,-1,z[0]],[1,-1,z[1]],[1,1,z[1]],[-1,1,z[0]]],
 faces:[[0,1,2],[0,2,3]],color,opacity}});
const state=assets=>({bounds:[-1.3,-1.3,-1.3,1.3,1.3,1.3],referenceGridVisible:false,
 objects:assets.map(a=>({id:a.id,kind:'beam',entity_ref:'element:'+a.id,metadata:{element_id:a.id}})),
 geometryAssets:assets,geometryPayloads:[],visibleObjectIds:assets.map(a=>a.id)});
function pixel(graph,point=[0,0,0]) {
 const v=graph.camera.position.clone().set(...point).project(graph.camera);
 const gl=canvas.getContext('webgl2'),result=new Uint8Array(4);
 gl.readPixels(Math.floor((v.x+1)*gl.drawingBufferWidth/2),Math.floor((v.y+1)*gl.drawingBufferHeight/2),1,1,gl.RGBA,gl.UNSIGNED_BYTE,result);
 return [...result];
}
function snapshot(){const gl=canvas.getContext('webgl2'),p=new Uint8Array(canvas.width*canvas.height*4);gl.readPixels(0,0,canvas.width,canvas.height,gl.RGBA,gl.UNSIGNED_BYTE,p);return Array.from(p);}
function render(assets,view='positiveZ') { const graph=renderer.render(state(assets));renderer.setStandardView(view);return graph; }
const overlap=reverse=>{const a=[plane('red',[-.6,.6],'#e54242',.5),plane('blue',[.6,-.6],'#2469e5',.5)];return reverse?a.reverse():a;};
let cameraRequestId=100;
window.fixture={
 order(reverse,view='positiveZ'){render(overlap(reverse),view);return snapshot();},
 triangleOrder(reverse){const [a,b]=overlap(false),av=a.generation_config.vertices,bv=b.generation_config.vertices;
  const faces=[[0,1,2],[0,2,3],[4,5,6],[4,6,7]];
  render([{id:'combined',format:'mesh',object_ids:['combined'],generation_config:{vertices:[...av,...bv],
   faces:reverse?faces.reverse():faces,opacity:.5,color:'#ffffff',
   vertex_values:[0,0,0,0,1,1,1,1],legend:{range:{min:0,max:1},color_map:'cividis'}}}]);return snapshot();},
 // Keep identical bounds in the reference: helper light placement follows the
 // scene bounds, so removing a plane would change lighting as well as opacity.
 occlusion(z,fade=true){const assets=[plane('opaque',[z,z],'#2469e5'),plane('translucent',[0,0],'#e54242',fade?.5:0)];return pixel(render(assets));},
 orbit(){render(overlap(false));const start=performance.now();for(let i=0;i<20;i++)renderer.orbitBy(.07,.01);return (performance.now()-start)/20;},
 resize(){canvas.style.width='480px';canvas.style.height='360px';const g=render(overlap(false));
  const result={size:[canvas.width,canvas.height],pixel:pixel(g)};canvas.style.width='640px';canvas.style.height='520px';return result;},
 clipped(){const s=state(overlap(false));s.sectionBox={enabled:true,min:[-1.3,-1.3,-1.3],max:[0,1.3,1.3]};const g=renderer.render(s);renderer.setStandardView('positiveZ');return {left:pixel(g,[-.5,0,0]),right:pixel(g,[.5,0,0])};},
 highlight(){const s=state(overlap(false));s.selectedObjectIds=['red'];renderer.render(s);renderer.setStandardView('positiveZ');return snapshot();},
 camera(){
  // A foreground surface sits on the viewing ray, beyond the camera position
  // chosen for a 20 cm selection. It must remain visible rather than sliced off.
  const direction=[1,-1,.65].map(value=>value/Math.hypot(1,-1,.65));
  const center=direction.map(value=>value*3);
  const foreground=plane('foreground',[center[2],center[2]],'#2469e5');
  foreground.generation_config.vertices.forEach(point=>{point[0]+=center[0];point[1]+=center[1];});
  const s=state([plane('background',[0,0],'#e54242'),foreground]);
  s.camera={fitRequest:{id:++cameraRequestId,bounds:[-.1,-.1,-.1,.1,.1,.1]}};
  const graph=renderer.render(s),foregroundPixel=pixel(graph);
  const focusHeight=(graph.camera.top-graph.camera.bottom)/graph.camera.zoom;
  let minimumDepth=Infinity,maximumDepth=-Infinity;
  for(let step=0;step<48;step++){
   if(step)renderer.orbitBy(Math.PI/12,step%2 ? -.04 : .04);
   for(const asset of s.geometryAssets)for(const point of asset.generation_config.vertices){
    const v=graph.camera.position.clone().set(...point).project(graph.camera);
    minimumDepth=Math.min(minimumDepth,v.z);maximumDepth=Math.max(maximumDepth,v.z);
   }
  }
  return {foregroundPixel,focusHeight,minimumDepth,maximumDepth,near:graph.camera.near,far:graph.camera.far};
 },
 cameraResize(){
  const asset=plane('wide',[0,0],'#2469e5');asset.generation_config.vertices.forEach(point=>point[0]*=5);
  const s=state([asset]),graph=renderer.render(s);renderer.setStandardView('positiveZ');
  canvas.style.width='300px';renderer.render(s);
  const projected=asset.generation_config.vertices.map(point=>graph.camera.position.clone().set(...point).project(graph.camera).toArray());
  const size=[canvas.width,canvas.height];canvas.style.width='640px';renderer.render(s);
  return {projected,size};
 },
 async cameraInspector(){
  const asset=plane('wide',[0,0],'#2469e5');asset.generation_config.vertices.forEach(point=>point[0]*=5);
  const graph=renderer.render(state([asset]));renderer.setStandardView('positiveZ');
  inspector.hidden=false;
  // No state render or canvas resize: the overlay's observer must redraw it.
  await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));
  const screenXs=asset.generation_config.vertices.map(point=>(graph.camera.position.clone().set(...point).project(graph.camera).x+1)*canvas.clientWidth/2);
  const insets=getViewportInsets(canvas,{right:inspector});
  inspector.hidden=true;
  await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));
  const restored=graph.camera.userData.viewportInsets;
  return {screenXs,insets,restored};
 },
 profile(){const vertices=[[0,-.25,-.25],[0,.25,-.25],[0,.25,.25],[0,-.25,.25],[2,-.25,-.25],[2,.25,-.25],[2,.25,.25],[2,-.25,.25]];
 const faces=[[0,1,5],[0,5,4],[1,2,6],[1,6,5],[2,3,7],[2,7,6],[3,0,4],[3,4,7],[0,3,2],[0,2,1],[4,5,6],[4,6,7]];
 renderer.render({...state([{id:'square',format:'mesh',object_ids:['square'],generation_config:{vertices,faces,color:'#8999ab',source:'tuba.element'}}]),bounds:[0,-.4,-.4,2,.4,.4]});renderer.setStandardView('iso');}
};
document.querySelector('#overlap').onclick=()=>fixture.order(false);document.querySelector('#profile').onclick=()=>fixture.profile();
document.querySelector('#camera').onclick=()=>fixture.camera();
fixture.order(false);
</script></body></html>`;
const server=await createServer({configFile:false,root,logLevel:'error',
 plugins:[{name:'rendering-diagnostics',configureServer(server){
  server.middlewares.use('/__rendering-review',(_request,response)=>{
   response.setHeader('content-type','text/html');response.end(html);
  });
 }}],
 cacheDir:resolve(output,'.vite'),server:{host:'127.0.0.1',port:5186,strictPort:true,
 fs:{allow:[root,realpathSync(resolve(root,'viewer/node_modules'))]}}});
await server.listen();
if(process.argv.includes('--serve')) {
 console.log('Rendering diagnostics: http://127.0.0.1:5186/__rendering-review');
} else {
 let browser;
 try {
  browser=await chromium.launch({headless:true});
  const page=await browser.newPage({viewport:{width:1000,height:800}});
  page.setDefaultNavigationTimeout(60_000);
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  page.on('console',m=>{if(m.type()==='error')errors.push(m.text());});
  const response=await page.goto('http://127.0.0.1:5186/__rendering-review',{waitUntil:'domcontentloaded'});
  const headers=await response.allHeaders();
  assert.match(headers['content-type'],/text\/html/);
  await page.waitForFunction(()=>Boolean(window.fixture),null,{timeout:45_000});
  const differences=[];
  for(const view of ['positiveZ','negativeZ','iso']) {
   const difference=await page.evaluate(v=>{
    const a=fixture.order(false,v),b=fixture.order(true,v);
    let delta=0;for(let i=0;i<a.length;i++)if(i%4!==3)delta=Math.max(delta,Math.abs(a[i]-b[i]));
    return delta;
   },view);
   if(view==='positiveZ')await page.screenshot({path:resolve(output,'transparent-overlap.png')});
   differences.push(difference);
  }
  const transparency=await page.locator('#canvas').getAttribute('data-transparency');
  const triangleDifference=await page.evaluate(()=>{
   const a=fixture.triangleOrder(false),b=fixture.triangleOrder(true);
   let delta=0;for(let i=0;i<a.length;i++)if(i%4!==3)delta=Math.max(delta,Math.abs(a[i]-b[i]));return delta;
  });
  const resized=await page.evaluate(()=>fixture.resize());
  const front=await page.evaluate(()=>fixture.occlusion(.5,true));
  const plain=await page.evaluate(()=>fixture.occlusion(.5,false));
  const behind=await page.evaluate(()=>fixture.occlusion(-.5,true));
  const orbitMs=await page.evaluate(()=>fixture.orbit());
  await page.evaluate(()=>{fixture.highlight();});
  await page.screenshot({path:resolve(output,'transparent-selected.png')});
  const clipped=await page.evaluate(()=>fixture.clipped());
  await page.screenshot({path:resolve(output,'transparent-clipped.png')});
  await page.evaluate(()=>fixture.profile());
  await page.screenshot({path:resolve(output,'square-profile.png')});
  const camera=await page.evaluate(()=>fixture.camera());
  await page.screenshot({path:resolve(output,'camera-focused-orbit.png')});
  const cameraResize=await page.evaluate(()=>fixture.cameraResize());
  const cameraInspector=await page.evaluate(()=>fixture.cameraInspector());
  const report={url:response.url(),contentType:headers['content-type'],
   differences,triangleDifference,resized,front,plain,behind,clipped,orbitMs,camera,cameraResize,cameraInspector,errors,transparency};
  writeFileSync(resolve(output,'rendering-smoke.json'),JSON.stringify(report,null,2));
  console.log(JSON.stringify(report));
  assert.deepEqual(errors,[],'WebGL must not report shader or browser errors');
  assert.ok(differences.every(delta=>delta<=2),'transparent color must not depend on asset insertion order at any view');
  assert.ok(triangleDifference<=2,'transparent color must not depend on triangle order inside a mesh');
  assert.deepEqual(resized.size,[480,360]);
  assert.ok(resized.pixel[0]>0 && resized.pixel[2]>0 && resized.pixel[0]<240,'resized render targets must still composite the surfaces');
  assert.deepEqual(front,plain,'opaque foreground must stay unobscured');
  assert.ok(behind[0]>plain[0]+10 && behind[2]<plain[2]-10,'opaque background must remain visible, tinted through the translucent surface');
  assert.deepEqual(clipped.right,[248,250,252,255],'section clipping must remove the right half of both transparent surfaces');
  assert.ok(clipped.left[0]<240 && clipped.left[2]<240,'the unclipped half must remain visible');
  assert.ok(camera.foregroundPixel[2]>camera.foregroundPixel[0]+40,'a focused view must still draw the surface in front of the selection');
  assert.ok(camera.focusHeight<1,'keeping the scene in depth must not zoom out the selection');
  assert.ok(camera.minimumDepth>-1 && camera.maximumDepth<1,'every surface must stay between the camera planes throughout orbit');
  assert.ok(camera.far-camera.near<20,'depth precision must follow the displayed scene size');
  assert.equal(cameraResize.size[0],300);
  assert.ok(cameraResize.projected.every(point=>Math.abs(point[0])<1 && Math.abs(point[1])<1),'the fitted scene must stay within a narrowed canvas');
  assert.equal(cameraInspector.insets.right,240);
  assert.ok(cameraInspector.screenXs.every(x=>x>0 && x<400),'a floating inspector must not cover fitted geometry');
  assert.deepEqual(cameraInspector.restored,{},'closing the overlay must restore the full viewport');
 } finally { await browser?.close();await server.close(); }
}
