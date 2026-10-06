import * as THREE from "three";
import { FullScreenQuad } from "three/examples/jsm/postprocessing/Pass.js";

// Weighted blended OIT (McGuire/Bavoil, JCGT 2013). Opaque depth is exact;
// overlapping translucent colors are approximate, but independent of triangle
// and object submission order. Two blend passes work on WebGL2 without the
// per-attachment blending extension. X-ray annotations remain a final overlay.
export class TransparencyRenderer {
  constructor(renderer) {
    this.renderer = renderer;
    this.supported = renderer.extensions.has("EXT_color_buffer_float");
    this.materials = new WeakMap();
    this.targets = null;
    this.uniforms = {
      tubaOpaqueDepth:{value:null},
      tubaViewport:{value:new THREE.Vector2()}
    };
    this.quad = new FullScreenQuad(new THREE.ShaderMaterial({
      uniforms:{opaque:{value:null},accumulation:{value:null},revealage:{value:null}},
      depthTest:false,depthWrite:false,blending:THREE.NoBlending,
      vertexShader:`varying vec2 vUv;
        void main(){vUv=uv;gl_Position=vec4(position.xy,0.0,1.0);}`,
      fragmentShader:`uniform sampler2D opaque,accumulation,revealage;
        varying vec2 vUv;
        void main(){
          vec4 sum=texture2D(accumulation,vUv);
          float transmission=clamp(texture2D(revealage,vUv).r,0.0,1.0);
          vec3 surface=sum.rgb/max(sum.a,0.00001);
          gl_FragColor=vec4(mix(surface,texture2D(opaque,vUv).rgb,transmission),1.0);
          #include <tonemapping_fragment>
          #include <colorspace_fragment>
        }`
    }));
  }

  ensureTargets() {
    const size=this.renderer.getDrawingBufferSize(new THREE.Vector2());
    if(!this.targets) {
      const options={type:THREE.HalfFloatType,minFilter:THREE.NearestFilter,
        magFilter:THREE.NearestFilter,depthBuffer:true};
      const opaque=new THREE.WebGLRenderTarget(size.x,size.y,options);
      opaque.depthTexture=new THREE.DepthTexture(size.x,size.y,THREE.UnsignedIntType);
      this.targets={opaque,accumulation:new THREE.WebGLRenderTarget(size.x,size.y,options),
        revealage:new THREE.WebGLRenderTarget(size.x,size.y,options)};
      for(const [name,target] of Object.entries(this.targets)) this.quad.material.uniforms[name].value=target.texture;
    }
    for(const target of Object.values(this.targets)) {
      if(target.width!==size.x || target.height!==size.y)target.setSize(size.x,size.y);
    }
    this.uniforms.tubaOpaqueDepth.value=this.targets.opaque.depthTexture;
    this.uniforms.tubaViewport.value.copy(size);
  }

  materialFor(source,accumulate) {
    let entry=this.materials.get(source);
    if(!entry) {
      entry={clones:[source.clone(),source.clone()],version:-1};
      this.materials.set(source,entry);
      const disposed=()=>{
        entry.clones.forEach(material=>material.dispose());
        this.materials.delete(source);
        source.removeEventListener("dispose",disposed);
      };
      source.addEventListener("dispose",disposed);
    }
    const material=entry.clones[accumulate?0:1];
    const changed=entry.version!==source.version;
    // Opacity, scalar colors, clipping planes and focus can change between
    // draws without changing the geometry or the original material version.
    material.copy(source);
    material.transparent=true;
    material.depthWrite=false;
    material.forceSinglePass=true;
    material.blending=THREE.CustomBlending;
    material.blendEquation=THREE.AddEquation;
    material.blendSrc=accumulate?THREE.OneFactor:THREE.ZeroFactor;
    material.blendDst=accumulate?THREE.OneFactor:THREE.OneMinusSrcAlphaFactor;
    material.blendEquationAlpha=null;
    material.blendSrcAlpha=null;
    material.blendDstAlpha=null;
    material.premultipliedAlpha=false;
    material.onBeforeCompile=(shader,renderer)=>{
      source.onBeforeCompile(shader,renderer);
      Object.assign(shader.uniforms,this.uniforms);
      shader.fragmentShader=`uniform sampler2D tubaOpaqueDepth;
        uniform vec2 tubaViewport;\n`+shader.fragmentShader;
      shader.fragmentShader=shader.fragmentShader.replace("#include <opaque_fragment>",`
        #include <opaque_fragment>
        float opaqueDepth=texture2D(tubaOpaqueDepth,gl_FragCoord.xy/tubaViewport).r;
        if(gl_FragCoord.z>opaqueDepth+0.000001)discard;
        float alpha=clamp(gl_FragColor.a,0.0,1.0);
        ${accumulate?`
          float weight=clamp(0.01+8.0*pow(1.0-gl_FragCoord.z,3.0),0.01,8.0);
          gl_FragColor=vec4(gl_FragColor.rgb*alpha,alpha)*weight;
        `:`gl_FragColor=vec4(alpha);`}`)
        .replace("#include <tonemapping_fragment>","")
        .replace("#include <colorspace_fragment>","")
        .replace("#include <premultiplied_alpha_fragment>","")
        .replace("#include <dithering_fragment>","");
    };
    material.customProgramCacheKey=()=>`${source.customProgramCacheKey()}:tuba-oit-${accumulate}`;
    if(changed)entry.clones.forEach(clone=>{clone.needsUpdate=true;});
    entry.version=source.version;
    return material;
  }

  render(scene,camera,target=null) {
    const renderer=this.renderer;
    const drawables=[];
    scene.traverseVisible(object=>{
      if(!object.material)return;
      const materials=Array.isArray(object.material)?object.material:[object.material];
      // Viewer surfaces use one material. Leave custom shaders and mixed
      // material arrays on their conventional path rather than rewriting them.
      const weighted=materials.length===1 && !materials[0].isShaderMaterial &&
        materials[0].visible && materials[0].transparent && materials[0].opacity<1 &&
        materials[0].depthTest;
      drawables.push({object,material:object.material,mask:object.layers.mask,
        mode:weighted?"weighted":materials.every(m=>!m.depthTest)?"overlay":"opaque"});
    });
    const hasTransparency=drawables.some(part=>part.mode==="weighted");
    renderer.domElement.dataset.transparency=hasTransparency?(this.supported?"weighted":"sorted-fallback"):"opaque";
    if(!hasTransparency || !this.supported) {
      renderer.setRenderTarget(target);
      renderer.clear();
      renderer.render(scene,camera);
      return;
    }
    this.ensureTargets();
    const oldTarget=renderer.getRenderTarget();
    const background=scene.background;
    const clearColor=renderer.getClearColor(new THREE.Color());
    const clearAlpha=renderer.getClearAlpha();
    const autoClear=renderer.autoClear;
    renderer.autoClear=false;
    // Layer masks suppress a draw without hiding its descendants: an opaque
    // edge can be a child of a translucent surface and still needs its pass.
    const only=mode=>drawables.forEach(part=>{part.object.layers.mask=part.mode===mode?part.mask:0;});
    try {
      only("opaque");
      renderer.setRenderTarget(this.targets.opaque);
      renderer.clear();
      renderer.render(scene,camera);
      scene.background=null;
      only("weighted");
      for(const [name,accumulate,clear] of [["accumulation",true,0],["revealage",false,1]]) {
        for(const part of drawables.filter(part=>part.mode==="weighted")) {
          part.object.material=this.materialFor(part.material,accumulate);
        }
        renderer.setRenderTarget(this.targets[name]);
        renderer.setClearColor(clear?0xffffff:0,clear);
        renderer.clear();
        renderer.render(scene,camera);
      }
      renderer.setRenderTarget(target);
      this.quad.render(renderer);
      only("overlay");
      if(drawables.some(part=>part.mode==="overlay"))renderer.render(scene,camera);
    } finally {
      for(const part of drawables) {
        part.object.layers.mask=part.mask;
        part.object.material=part.material;
      }
      scene.background=background;
      renderer.setClearColor(clearColor,clearAlpha);
      renderer.autoClear=autoClear;
      renderer.setRenderTarget(oldTarget);
    }
  }
}
