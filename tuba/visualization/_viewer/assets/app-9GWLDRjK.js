import{a as e,i as t,n,o as r,r as i,t as a}from"./index-CRG_epNb.js";var o=/^(\s*[A-Za-z_][\w.]*\.run\(\s*)(-?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?)(\s*\)\s*(?:#.*)?)$/;function s(e){let t=o.exec(e??``);return t?Number(t[2]):null}function c(e,t){let n=Number.isInteger(t)?`${t}.0`:String(t);return e.replace(o,(e,t,r,i)=>`${t}${n}${i}`)}function l(e){return(e??``).split(`
`).length}function u(e,t){return(e??``).split(`
`)[t-1]??``}function d(e,t,n){let r=e.split(`
`);return!Number.isInteger(t)||t<1||t>r.length?e:(r[t-1]=n,r.join(`
`))}function f(e,t){let n=e.split(`
`),r=0;for(let e=0;e<t-1&&e<n.length;e+=1)r+=n[e].length+1;return r}function p(e,t){return e.slice(0,t).split(`
`).length}function m(e){let t=e?.entity_ref??e?.metadata?.source_ref;return typeof t==`string`&&t.startsWith(`element:`)&&!String(e.kind).includes(`node`)&&!String(e.kind).endsWith(`_vector`)&&e.kind!==`applied_load`?t:e?.id}function h(e,t){let n=new Set(t),r=new Set((e.objects??[]).filter(e=>n.has(e.id)).map(m));return(e.objects??[]).filter(e=>n.has(e.id)||r.has(m(e))).map(e=>e.id)}function g(e,t){let n=m(e.objects.find(e=>e.id===t));return n&&n!==t?_(e,n)??t:t}function _(e,t){if(typeof t!=`string`||t.length===0)return null;let n=Array.isArray(e?.objects)?e.objects:[],r=new Map(n.map(e=>[e.id,e]));if(r.has(t))return t;let i=`object:${t}`;if(r.has(i))return i;let a=v(e?.objectMap,t,r),o=new Map((e?.geometryAssets??[]).map(e=>[e.id,e])),s=[];for(let e of n){let n=e.entity_ref===t||e.metadata?.entity_ref===t,r=a.has(e.id),i=y(e,t,o);if(!n&&!r&&!i)continue;let c=o.get(e.geometry_asset_id);s.push({id:e.id,rank:b(e,c)||i?1:0})}return s.sort((e,t)=>e.rank-t.rank||x(e.id,t.id)),s[0]?.id??null}function v(e,t,n){let r=new Set;if(!e||typeof e!=`object`||Array.isArray(e))return r;let i=e[t],a=typeof i==`string`?i:i?.object_id??i?.objectId??i?.id;n.has(a)&&r.add(a);for(let[i,a]of Object.entries(e))n.has(i)&&(typeof a==`string`?a:a?.entity_ref??a?.entityRef??a?.metadata?.entity_ref)===t&&r.add(i);return r}function y(e,t,n){if(!t.startsWith(`analysis_node:`))return!1;let r=t.slice(14);if(!r)return!1;let i=e.source?.analysis_mesh,a=e.kind===`analysis_mesh_node`||i?.member_type===`node`,o=e.metadata?.member_id===r||i?.member_id===r,s=n.get(e.geometry_asset_id);return a&&o&&[`point`,`marker`,`vector`].includes(s?.format)}function b(e,t){let n=String(e.kind??``);return n.includes(`analysis_mesh`)||n.includes(`marker`)||n.endsWith(`_vector`)||n===`deformed_centerline`||n===`physical_envelope`||[`point`,`marker`,`vector`,`line_load_comb`].includes(t?.format)}function x(e,t){return e===t?0:e<t?-1:1}function S(e){let t=new Map,n=Array.isArray(e?.provenance)?e.provenance:[];for(let e of n){if(e?.kind!==`study`)continue;let n=e?.metadata?.solver_input_identity?.load_case,r=e?.files?.comm;typeof n==`string`&&n&&typeof r==`string`&&r&&(t.has(n)||t.set(n,{name:n,uri:r}))}return t}function C(e,t){let n=e?.source_uri;if(typeof n!=`string`||!n)return null;let r=S(t),i=[],a=Array.isArray(e?.solver_input_identities)?e.solver_input_identities:[];for(let e of a){let t=typeof e?.load_case==`string`?r.get(e.load_case):null;t&&!i.includes(t)&&i.push(t)}for(let e of r.values())i.includes(e)||i.push(e);return{scriptUri:n,loadCases:i}}var w=`engineering`,T=Object.freeze([{id:`engineering`,label:`SI · mm · MPa`,title:`Engineering: mm · MPa · kN`},{id:`si`,label:`SI · m · Pa`,title:`SI base: m · Pa · N`}]),E=Object.freeze({length:{si:{unit:`m`,factor:1},engineering:{unit:`mm`,factor:1e3}},stress:{si:{unit:`Pa`,factor:1},engineering:{unit:`MPa`,factor:1e-6}},force:{si:{unit:`N`,factor:1},engineering:{unit:`kN`,factor:.001}},moment:{si:{unit:`N·m`,factor:1},engineering:{unit:`kN·m`,factor:.001}}}),D=Object.freeze({m:`length`,Pa:`stress`,N:`force`,"N*m":`moment`,"N.m":`moment`,"N-m":`moment`});function O(e){let t=e?.unitSystem;return T.some(e=>e.id===t)?t:w}function k(e,t){return T.some(e=>e.id===t)?{...e,unitSystem:t}:e}function A(e){return T[(T.findIndex(t=>t.id===O(e))+1)%T.length].id}function ee(e,t){return E[D[String(e??``).trim()]]?.[t]??null}function te(e){return ee(e,w)!==null}function j(e,t=w){return ee(e,t)?.unit??String(e??``)}function ne(e){if(e==null||e===``)return NaN;let t=Number(e);return Number.isFinite(t)?t:NaN}function M(e,t,n=w){let r=ne(e),i=ee(t,n);return!Number.isFinite(r)||!i?r:r*i.factor}function re(e,t,n=w){let r=ne(e),i=ee(t,n);return!Number.isFinite(r)||!i?r:r/i.factor}function N(e,t,n=w){let r=oe(M(e,t,n));if(!r)return``;let i=j(t,n);return i?`${r} ${i}`:r}function ie(e,t,n=w){return oe(M(e,t,n))}function ae(e){let t=Math.floor(ne(e)/1e3);if(!Number.isFinite(t)||t<0)return``;let n=String(t%60).padStart(2,`0`),r=Math.floor(t/60)%60,i=Math.floor(t/3600);return i?`${i}:${String(r).padStart(2,`0`)}:${n}`:`${r}:${n}`}function oe(e){let t=ne(e);if(!Number.isFinite(t))return``;if(t===0)return`0`;let n=Math.abs(t);return n>=1e6||n<1e-4?t.toExponential(2):String(Number(t.toPrecision(4)))}var se={temperature:`°C`,pressure:`Pa`,wind:`Pa`,line_load:`N/m`};function ce(e){return(e.overlays??[]).filter(e=>e.kind===`load_case`).map(e=>e.data)}function le(e){if(e.group)return e.group;if(e.route_id){let t=e.station_start!=null||e.station_end!=null?` (${e.station_start??`start`}–${e.station_end??`end`} m)`:``;return e.route_id+t}return e.scope===`nodes`?(e.node_ids??[]).join(`, `):e.scope===`elements`?(e.element_ids??[]).join(`, `):`All pipes`}function ue(e,t){let n=new Set(t.affected_element_ids??t.element_ids??[]);return(e.objects??[]).filter(e=>[`pipe`,`element`,`rack_member`].includes(e.kind)&&typeof e.entity_ref==`string`&&e.entity_ref.startsWith(`element:`)&&n.has(e.entity_ref.slice(8))).map(e=>e.id)}function de(e,t){if(typeof t?.entity_ref!=`string`||!t.entity_ref.startsWith(`element:`))return null;let n=ce(e).find(t=>t.load_case===e.activeLoadCase);if(!n?.fields)return null;let r=t.entity_ref.slice(8),i=n.fields.filter(e=>(e.affected_element_ids??e.element_ids??[]).includes(r)),a=O(e),o=[];for(let e of[`temperature`,`pressure`]){let t=i.filter(t=>t.quantity===e);t.length||o.push({label:`${e} · case default`,value:N(e===`pressure`?n.internal_pressure_pa:n.temperature_c,se[e],a),sourceLine:n.source_line});for(let n of t)o.push({label:`${e} · ${le(n)}`,value:`${N(n.value,se[e],a)}${n.profile===`linear`?` (profile endpoint)`:``}`,sourceLine:n.source_call_line??n.source_line})}return o.push({kind:`note`,label:`Authored assignments; node temperatures interpolate along connected elements.`}),{title:`Inputs · ${n.load_case}`,lines:o}}function fe(e,t,{select:n,sourceLink:r,compare:i=!1}={}){e.replaceChildren();let a=ce(t),o=a.find(e=>e.load_case===t.activeLoadCase);if(!o){e.textContent=`This bundle has no input assignments for the selected case.`;return}let s=O(t),c=(e,t)=>N(e,se[t],s),l=document.createElement(`p`);l.className=`case-defaults`,l.textContent=`Defaults: ${c(o.temperature_c,`temperature`)} · ${c(o.internal_pressure_pa,`pressure`)} · reference ${c(o.ref_temperature_c,`temperature`)} · self-weight ${o.gravity?`on`:`off`}`;let u=r?.(o.source_line);if(u&&l.append(` `,u),e.append(l),a.some(e=>(i||e===o)&&e.field_count>0&&!Array.isArray(e.fields))){let t=document.createElement(`p`);t.textContent=`This bundle records local fields without their assignments. Rebuild the review to inspect them; the defaults are not the values everywhere.`,e.append(t);return}let d=o.fields??[],f=document.createElement(`table`);f.className=`case-input-table`,f.setAttribute(`aria-label`,i?`Assignments across load cases`:`${o.load_case} input assignments`);let p=f.createTHead().insertRow();for(let e of[`Assignment`,...i?a.map(e=>e.load_case):[`Value`]]){let t=document.createElement(`th`);t.scope=`col`,t.textContent=e,p.append(t)}let m=f.createTBody();if(i){for(let[e,t,n]of[[`Default temperature`,`temperature_c`,`temperature`],[`Default pressure`,`internal_pressure_pa`,`pressure`],[`Reference temperature`,`ref_temperature_c`,`temperature`]]){let r=m.insertRow();r.insertCell().textContent=e;for(let e of a)r.insertCell().textContent=c(e[t],n)}let e=m.insertRow();e.insertCell().textContent=`Self-weight`;for(let t of a)e.insertCell().textContent=t.gravity?`On`:`Off`}let h=e=>JSON.stringify([e.quantity,e.scope,e.profile,le(e),e.direction]),g=i?[...new Map(a.flatMap(e=>(e.fields??[]).map(e=>[h(e),e]))).values()]:d;for(let[s,l]of g.entries()){let u=m.insertRow(),d=u.insertCell(),f=document.createElement(`button`);f.type=`button`,f.className=`case-assignment`,f.dataset.focusKey=`${e.dataset.caseInputs}:assignment:${s}`,f.textContent=`${l.quantity} · ${le(l)}`,f.title=`Select affected elements in 3D`;let p=ue(t,l);if(f.disabled=!p.length,f.setAttribute(`aria-pressed`,String(p.length>0&&p.every(e=>(t.selectedObjectIds??[]).includes(e)))),f.addEventListener(`click`,()=>n?.(p)),d.append(f),!i){let e=r?.(l.source_call_line??l.source_line);e&&d.append(` `,e)}for(let e of i?a:[o]){let t=i?(e.fields??[]).find(e=>h(e)===h(l)):l,n=u.insertCell();n.textContent=t?c(t.value,t.quantity):`—`,t?.scope===`nodes`?n.append(` at node`):t?.profile===`linear`&&n.append(` · linear endpoint`),t?.direction&&n.append(` · direction [${t.direction.join(`, `)}]`)}}(g.length||i)&&e.append(f);let _=document.createElement(`p`);_.className=`case-input-note`,_.textContent=i?`— means no matching assignment; inspect that case's defaults and other assignments.`:d.length?`Authored inputs. Select an assignment to highlight its scope; line links open model.py. Unassigned regions use the defaults. Node temperatures interpolate along connected elements.`:`Uniform inputs: every region uses the case defaults.`,e.append(_)}var pe=`field:envelope`;function me(e){return(e.resultStates??[]).filter(t=>{let n=t.data?.load_case;return!e.activeLoadCase||!n||n===e.activeLoadCase}).map(e=>({id:e.data?.id??e.id,label:e.name??e.data?.load_case??e.id}))}function he(e){return me(e).length>1}function ge(e,t,n=`magnitude`){if(!t)return[];let r=t.field??t.label??null,i=t.unit??null,a=t.result_type??null;return(e.overlays??[]).filter(t=>{if(t.kind!==`solver_result`)return!1;let n=t.data??{};if(e.activeLoadCase&&n.load_case&&n.load_case!==e.activeLoadCase||n.result_type&&a&&n.result_type!==a)return!1;let o=n.field??n.result_type??t.name??t.id;return r&&o!==r||i&&n.unit&&n.unit!==i?!1:ye(n.values)})}function _e(e,t,n=`magnitude`,r=null){let i=ge(e,t),a={},o={},s=new Set;for(let e of i){let t=e.data??{},i=t.result_state_id??null;for(let[e,c]of Object.entries(t.values??{})){let t=r?r(c,n):Number(Array.isArray(c)?c[0]:c);Number.isFinite(t)&&(s.add(i),(!Number.isFinite(a[e])||t>a[e])&&(a[e]=t,o[e]=i))}}let c=Object.values(a).filter(Number.isFinite);return{values:a,winners:o,range:c.length>0?{min:Math.min(...c),max:Math.max(...c)}:null,resultStateIds:[...s].filter(Boolean),component:n,enveloped:s.size>1}}function ve(e){return e?.id===pe}function ye(e){return e&&typeof e==`object`&&Object.keys(e).length>0}function be(e){return e.resultFields??[]}function P(e,t=Se(e)){let n=F(e).filter(e=>!t||!e.load_case||e.load_case===t).map(e=>({id:e.id,label:Re(e),support:e.support,components:e.components??[`magnitude`],field:e})),r=xe(e,t);return r?[...n,r]:n}function xe(e,t){if(!he(e))return null;let n=me(e).length,r=F(e).filter(e=>!t||!e.load_case||e.load_case===t).map(e=>({field:e.id,label:Re(e),unit:e.unit}));return r.length===0?null:{id:pe,label:`Envelope — worst of ${n} result steps`,support:`envelope`,components:[`magnitude`],envelope:!0,field:{id:pe,label:`Envelope`,support:`envelope`,components:[`magnitude`],load_case:t??null,unit:r[0]?.unit??``,compliance_role:`derived_envelope_not_a_solver_result`,envelope_source:r}}}function Se(e){return e.coloring?.loadCase??be(e)[0]?.load_case??null}function Ce(e){let t=F(e),n=be(e).find(t=>t.id===e.coloring?.fieldId),r=xe(e,Se(e));if(e.coloring?.fieldId===`field:envelope`)return r??t.find(t=>t.load_case===Se(e))??t[0]??null;let i=t.find(e=>e.id===n?.id);if(i)return i;if(n){let r=t=>{let n=(e.overlays??[]).find(e=>e.id===t.overlay_id);return JSON.stringify([n?.data?.field??n?.data?.result_type??t.label,t.support,t.unit])},i=t.find(e=>r(e)===r(n));if(i)return i}let a=Se(e);return t.find(e=>e.load_case===a)??t[0]??null}function F(e){let t=new Map((e.overlays??[]).map(e=>[e.id,e])),n=e.activeLoadCase??e.coloring?.loadCase;return be(e).filter(r=>{let i=t.get(r.overlay_id)?.data?.result_state_id??r.result_state_id;return(!n||!r.load_case||r.load_case===n)&&(!e.activeResultStateId||!i||i===e.activeResultStateId)})}function we(e){let t=Ce(e)?.components??[`magnitude`],n=e.coloring?.component;return t.includes(n)?n:t[0]}function I(e){return(Ce(e)?.components??[`magnitude`]).length>1}function L(e,t){let n={...e.coloring??{},loadCase:t??null};return De({...e,coloring:n})}function Te(e,t){let n=be(e).find(e=>e.id===t);return{...De({...e,coloring:{...e.coloring??{},fieldId:t??null,loadCase:n?.load_case??e.coloring?.loadCase??null}}),colorChannel:`results`}}function Ee(e,t){return{...De({...e,coloring:{...e.coloring??{},component:t??null}}),colorChannel:`results`}}function De(e){let t=Ce(e),n={loadCase:t?.load_case??Se(e)??null,fieldId:t?.id??null,component:e.coloring?.component??null};return n.component=we({...e,coloring:n}),{...e,coloring:n}}function Oe(e){return De({...e,coloring:e.coloring??{}}).coloring}function ke(e){let t=Ce(e);if(!t)return null;if(ve(t)){let n=_e(e,Pe(e,t),we(e),Ie);return n.range?{fieldId:t.id,field:`Envelope`,component:n.component,support:`envelope`,unit:t.unit??``,loadCase:t.load_case??null,range:n.range,complianceRole:`derived_envelope_not_a_solver_result`,envelope:{...n,sources:t.envelope_source??[],resultStates:me(e)},overlay:null}:null}let n=(e.overlays??[]).find(e=>e.id===t.overlay_id),r=((t.components??[`magnitude`]).length===1?t.range:null)??Le(Object.values(Me(e)));if(!r)return null;let i=we(e);return{fieldId:t.id,field:Re(t),component:i,support:t.support,unit:Ae(t,i),loadCase:t.load_case??null,range:{min:r[0],max:r[1]},complianceRole:t.compliance_role??null,overlay:n}}function Ae(e,t){return[`MT`,`MFY`,`MFZ`,`MX`,`MY`,`MZ`].includes(t)?`N·m`:[`N`,`VY`,`VZ`,`FX`,`FY`,`FZ`].includes(t)?`N`:[`DRX`,`DRY`,`DRZ`].includes(t)?`rad`:e.unit??``}function je(e){let t=Ce(e),n=t?.compliance_role??(t?.label?.toLowerCase()===`fe vmis (not code stress)`?`visualization_only_not_asme_code_stress`:null);return n?n===`visualization_only_not_asme_code_stress`?`FE stress - not ASME code stress`:n===`derived_envelope_not_a_solver_result`?`Envelope - the worst of the result steps, not a separate solve`:n.replace(/_/g,` `):null}function Me(e){let t=Ce(e);if(!t)return{};if(ve(t))return _e(e,Pe(e,t),we(e),Ie).values;let n=(e.overlays??[]).find(e=>e.id===t.overlay_id)?.data?.values??{},r=we(e),i={};for(let[e,t]of Object.entries(n)){let n=Ie(t,r);Number.isFinite(n)&&(i[e]=n)}return i}function Ne(e){let t=Ce(e);return ve(t)?{..._e(e,Pe(e,t),we(e),Ie),resultStates:me(e)}:null}function Pe(e,t){let n=t.load_case??Se(e),r=F(e).filter(e=>!n||!e.load_case||e.load_case===n);return r.find(e=>e.support===`cell`)??r.find(e=>e.support!==`node`)??r[0]??null}var Fe={DX:0,DY:1,DZ:2,FX:0,FY:1,FZ:2,MX:0,MY:1,MZ:2,DRX:3,DRY:4,DRZ:5,N:0,VY:1,VZ:2,MT:3,MFY:4,MFZ:5};function Ie(e,t){if(Array.isArray(e)){let n=Fe[t];return n!==void 0&&n<e.length?Number(e[n]):t===`magnitude`||!t?Math.hypot(...e.slice(0,Math.min(3,e.length)).map(Number)):Number(e[0])}return Number(e)}function Le(e){let t=e.filter(e=>Number.isFinite(e));return t.length>0?[Math.min(...t),Math.max(...t)]:null}function Re(e){let t={cell:`elements`,subpoint:`wall points`}[e.support]??e.support,n=t&&t!==`node`?` (${t})`:``,r=e.label||e.id;return`${{displacement:`Displacement`,reaction_force:`Reaction force`,reaction_moment:`Reaction moment`,"fe vmis":`Von Mises stress`,"fe vmis (not code stress)":`Von Mises stress`,stress:`Stress`}[String(r).toLowerCase().replace(/_magnitude$/,``)]??String(r).replaceAll(`_`,` `).replace(/^[a-z]/,e=>e.toUpperCase())}${n}`}var ze=Object.freeze([`model`,`results`]);function Be(e={}){return ze.includes(e.colorChannel)?e.colorChannel:Ve(e)?`results`:`model`}function Ve(e={}){return(e.resultFields??[]).length>0||(e.resultStates??[]).length>0?!0:(e.overlays??[]).some(e=>e.kind===`solver_result`||e.kind===`result_state`)}var He=Object.freeze({build:{design:!0,analysis_mesh:!0,results:!1,annotations:!1}});function Ue(e){return Object.hasOwn(He,e)?He[e]:null}var We=Object.freeze([`embed`,`build`,`review`]);function Ge(e={}){return e.embed?`embed`:We.includes(e.stage)?e.stage:`review`}function Ke(e={},t={}){let n=Ge(e),r=n===`review`;return{stage:n,railVisible:r&&t.railExpanded!==!1,railToggleVisible:r,scriptVisible:n===`build`,headerVisible:n!==`embed`,bundle:r&&t.studio?.hasReview?`review`:`build`,visibility:Ue(n)?n:null}}function qe(e={}){return e.hasReview&&!e.reviewStale?`review`:`build`}function Je({review:e=null,embed:t=!1}={}){return{review:e,embed:!!t}}var Ye=0,Xe=Object.freeze([1,1.5,2,2.5,3,4,5,6,8,10]),Ze=Object.freeze([Ye,4,6,8,9,12,16]);function Qe(e){if(!Number.isFinite(e)||e<=0)return 0;let t=10**Math.floor(Math.log10(e)),n=e/t,r=Xe[0];for(let e of Xe)Math.abs(n-e)<Math.abs(n-r)-1e-9&&(r=e);return Number((r*t).toPrecision(12))}function $e(e,t,n){let r=Number.isFinite(Number(e))?Number(e):0,i=Number.isFinite(Number(t))?Number(t):r;if(i<=r)return{min:r,max:r+1,step:1};let a=Qe((i-r)/Math.max(1,rt(n)));return a<=0?{min:r,max:i,step:0}:{min:Math.floor(r/a+1e-9)*a,max:Math.ceil(i/a-1e-9)*a,step:a}}function et(e){let{min:t,max:n}=tt(e),r=nt(e);if(r===Ye)return[t,n];let i=Qe((n-t)/r);if(i<=0)return[t,n];let a=[t],o=Math.min(Math.ceil((n-t)/i),4096);for(let e=1;e<=o;e+=1)a.push(t+e*i);return a}function tt(e){let t={min:ct(e?.range?.min,0),max:ct(e?.range?.max,0)},n=e?.rangeOverride??null,r=n&&Number.isFinite(Number(n.min))?Number(n.min):t.min,i=n&&Number.isFinite(Number(n.max))?Number(n.max):t.max;if(i<=r)return{min:r,max:r+1};let a=nt(e);if(a===Ye)return{min:r,max:i};let o=Qe((i-r)/a);return o<=0?{min:r,max:i}:{min:r,max:r+Math.min(Math.max(Math.ceil((i-r)/o),1),4096)*o}}function nt(e){return rt(e?.bands)}function rt(e){let t=Number(e);return!Number.isFinite(t)||t<2?Ye:Math.round(t)}function it(e,t){let{min:n,max:r}=tt(t);if(!Number.isFinite(e))return 0;if(nt(t)===Ye)return lt((e-n)/Math.max(r-n,1e-12),0,1);let i=et(t).length-1;if(i<2)return 0;let a=lt((e-n)/Math.max(r-n,1e-12),0,1);return Math.min(Math.floor(a*i),i-1)/(i-1)}function at(e){return!!e?.rangeOverride}function ot(e,t){if(!e)return e;let n=rt(t?.bands),r=st(t?.rangeOverride);return{...e,bands:n,rangeOverride:r,range:tt({...e,bands:n,rangeOverride:r})}}function st(e){if(!e)return null;let t=Number(e?.min),n=Number(e?.max);return!Number.isFinite(t)||!Number.isFinite(n)||n<=t?null:{min:t,max:n}}function ct(e,t){let n=Number(e);return Number.isFinite(n)?n:t}function lt(e,t,n){return Math.min(Math.max(e,t),n)}function ut(e){return Number.isFinite(e)?String(Number(e.toPrecision(8))):`unavailable`}function dt(e){let t=new Map;for(let n of[...e.resultStates??[],...e.geometryStates??[],...en(e),...(e.overlays??[]).filter(e=>e.kind===`load_case`)]){let e=n.data??{},r=e.load_case;!r||t.has(r)||t.set(r,{id:r,label:r,resultStateId:e.result_state_id??e.id??null})}return[...t.values()]}function ft(e){return(e.resultStates??[]).map(e=>{let t=e.data??{};return{id:t.id??e.id,label:t.metadata?.stage_label?`${t.metadata.stage_label} / ${ut(t.metadata.pseudo_time)}`:e.name||t.load_case||t.id||e.id,loadCase:t.load_case??null,stageIndex:Number.isFinite(t.metadata?.stage_index)?t.metadata.stage_index:null,stageLabel:t.metadata?.stage_label??null,pseudoTime:Number.isFinite(t.metadata?.pseudo_time)?t.metadata.pseudo_time:null,overlay:e}})}function pt(e){let t=ft(e),n=e.contactFindings?.primary??null,r=new Map;for(let e of t)e.stageIndex!=null&&(r.has(e.stageIndex)||r.set(e.stageIndex,[]),r.get(e.stageIndex).push(e));return[...r.entries()].sort(([e],[t])=>e-t).map(([e,t])=>{let r=n?.stages?.find(t=>t.index===e)??null;return{index:e,label:t[t.length-1].stageLabel??`Stage ${e}`,pseudoTime:t[t.length-1].pseudoTime??null,resultStateId:r?.result_state_id??t[t.length-1].id,firstResultStateId:t[0].id,resultStateIds:t.map(e=>e.id),incrementCount:t.length,findings:(n?.findings??[]).filter(t=>(t.stage_indices??[t.stage_index]).includes(e))}})}function mt(e){let t=vt(e);return Number.isFinite(t?.stageIndex)?t.stageIndex:null}function ht(e,t){let n=ft(t);if(n.length===0){let n=dt(t),r=e.activeLoadCase??e.coloring?.loadCase;return{activeResultStateId:null,activeLoadCase:n.find(e=>e.id===r)?.id??t.activeLoadCase??t.coloring?.loadCase??n[0]?.id??null}}let r=n.find(t=>t.id===e.activeResultStateId&&t.loadCase===e.activeLoadCase);if(r)return{activeResultStateId:r.id,activeLoadCase:r.loadCase};let i=n.find(t=>t.loadCase===e.activeLoadCase)??n.find(e=>e.id===t.activeResultStateId&&e.loadCase===t.activeLoadCase)??n.find(e=>e.id===t.activeResultStateId)??n.find(e=>e.loadCase===t.activeLoadCase)??n[0]??null;return{activeResultStateId:i?.id??null,activeLoadCase:i?.loadCase??t.activeLoadCase??null}}function gt(e,t=e.activeLoadCase??null){return(e.geometryStates??[]).filter(n=>{let r=n.data?.load_case??null,i=n.data?.result_state_id;return!t||(!r||r===t)&&(!e.activeResultStateId||!i||i===e.activeResultStateId)}).map(e=>{let t=e.data??{};return{id:t.id??e.id,label:_t(e),loadCase:t.load_case??null,purpose:t.purpose??null,stateType:t.state_type??null,visualScale:t.visual_scale??t.displacement_scale??null,overlay:e}})}function _t(e){let t=e.data??{},n=Number(t.visual_scale??t.displacement_scale),r=t.state_type===`operating`&&t.purpose===`engineering`?`actual deformation`:t.state_type===`deformed`||t.purpose===`visualization`?`${n>1?`exaggerated`:`displayed`} deformation${Number.isFinite(n)&&n>0?` (${n}×)`:``}`:t.state_type===`cold`?`reference geometry`:(t.state_type??e.name??`geometry`).replaceAll(`_`,` `);return t.load_case?`${t.load_case} — ${r}`:r[0].toUpperCase()+r.slice(1)}function vt(e){let t=ft(e);return t.find(t=>t.id===e.activeResultStateId)??t.find(t=>t.loadCase===xt(e))??t[0]??null}function yt(e){return e.reviewFocus===`contact`}function bt(e){return e.contactNeutral!==!1&&yt(e)}function xt(e){return e.activeLoadCase??e.resultStates?.[0]?.data?.load_case??en(e)[0]?.data?.load_case??null}function St(e){let t=xt(e);return(e.overlays??[]).find(e=>e.kind===`load_case`&&e.data?.load_case===t)?.data??null}function Ct(e,t=null){let n=vt(e),r=e.activeResultStateId??n?.id??null,i=xt(e);return en(e).filter(e=>{let n=e.data??{};return t&&n.result_type!==t||r&&n.result_state_id&&n.result_state_id!==r||i&&n.load_case&&n.load_case!==i?!1:e.visible!==!1})}function wt(e){return bt(e)?null:(e.resultFields??[]).length>0?ke(e)?.overlay??null:Ct(e,`tuyau_subpoints`)[0]??Ct(e,`stress`)[0]??Ct(e).find(e=>tn(e.data?.values))??null}function Tt(e,t){let n=t?.fieldId??t?.overlay?.id??null;return{bands:e.legendBands??0,rangeOverride:n?e.legendRanges?.[n]??null:null}}function Et(e){if(Be(e)!==`results`||bt(e))return null;if((e.resultFields??[]).length>0){let t=ke(e);return t?ot({...t,colorMap:t.overlay?.data?.legend?.color_map??`turbo`,...Dt(e)},Tt(e,t)):null}let t=wt(e);if(!t)return null;let n=t.data??{},r=nn(n.values),i=n.legend?.range??n.range??{min:Math.min(...r),max:Math.max(...r)};return ot({field:n.legend?.field??n.field??n.result_type??t.name??t.id,unit:n.legend?.unit??n.unit??``,range:i,colorMap:n.legend?.color_map??`turbo`,...Dt(e),declaredThresholds:n.legend?.thresholds??{},overlay:t},Tt(e,{overlay:t}))}function Dt(e){return{thresholds:{stress_min:rn(e.resultThreshold),utilization_min:rn(e.utilizationThreshold)}}}function Ot(e,t=wt(e)){return t?(e.resultFields??[]).length>0?Me(e):t.data?.values??{}:{}}function kt(e){if(Be(e)!==`results`)return[];let t=wt(e);if(!t)return[];let n=t.data??{},r=Ot(e,t),i=Array.isArray(n.hotspots)&&n.hotspots.length>0?n.hotspots:Object.entries(r).map(([e,t])=>({object_id:e,value:t,unit:n.unit})),a=rn(e.resultThreshold),o=rn(e.utilizationThreshold);return i.map(t=>{let i=t.object_id??t.objectId,a=(e.objects??[]).find(e=>e.id===i),o=Number(t.value??r[i]),s=rn(t.utilization??n.utilization_values?.[i]);return{objectId:i,objectName:a?.name??i,elementId:t.element_id??t.elementId,rowIndex:t.row_index??t.rowIndex,subpointIndex:t.subpoint_index??t.subpointIndex,unit:t.unit??n.unit??``,utilization:s,value:o}}).filter(e=>Number.isFinite(e.value)).filter(e=>a===null||e.value>=a).filter(e=>o===null||(e.utilization??0)>=o).sort((e,t)=>t.value-e.value)}var At=Object.freeze([.01,.05]);function jt(e,t=At){let n=Ct(e,`tuyau_subpoints`)[0];if(!n)return null;let r=n.data??{},i=Nt(e,n);if(i.length===0)return null;let a=[...i].sort((e,t)=>e-t),o=Number(r.total_count??a.length);return{unit:r.unit??`Pa`,count:a.length,declaredCount:Number.isFinite(o)?o:null,truncated:Number.isFinite(o)&&o>a.length,max:a[a.length-1],min:a[0],percentiles:t.map(e=>({fraction:e,value:Mt(a,1-e)}))}}function Mt(e,t){if(e.length===0)return null;let n=Math.ceil(t*e.length);return e[Math.min(Math.max(n-1,0),e.length-1)]}function Nt(e,t){let n=t.data?.result_state_id??null,r=[];for(let t of e.geometryPayloads??[]){let e=t.generation_config??{};if(!Array.isArray(e.values))continue;let i=e.result_state_id??null;if(!(n&&i&&i!==n))for(let t of e.values){let e=Number(t);Number.isFinite(e)&&r.push(e)}}return r}function Pt(e){return kt(e)}function Ft(e){return Pt(e).findIndex(t=>t.objectId===e.activeFindingObjectId)}function It(e,t){let n=Pt(e);if(n.length===0)return null;let r=Ft(e);return r===-1?n[t>0?0:n.length-1]:n[(r+t+n.length)%n.length]}function Lt(e,t,n=[]){if(Be(e)!==`results`)return null;let r=wt(e);if(!r)return null;let i=Array.isArray(t)?t:[t],a=Ot(e,r),o=(r.data?.vectors??[]).filter(e=>(e.object_ids??[]).some(e=>i.includes(e))).map(e=>e.node_id).filter(Boolean),s=[...i,...n,...o].map(e=>Number(a[e])).filter(e=>Number.isFinite(e));return s.length===0?null:zt(Math.max(...s),Et(e))}var Rt=Object.freeze([8268,12399,3754091,5725549,7369075,9078649,10919285,12891500,16771654]);function zt(e,t){if(!t||!Number.isFinite(e))return null;let n=it(e,t)*(Rt.length-1),r=Math.min(Math.floor(n),Rt.length-2);return an(Rt[r],Rt[r+1],n-r)}function Bt(e,t){let n=e.resultVectorScales?.[t];return Number.isFinite(Number(n))?Math.max(Number(n),0):1}function Vt(e){let t=Number(e.visualDeformationScale??1);return Number.isFinite(t)&&t>=0?t:1}function Ht(e,t){let n=ft(e).filter(e=>e.loadCase===t),r=n.find(t=>t.id===e.activeResultStateId)??n[0],i=gt(e,null).find(t=>t.id===e.activeGeometryStateId),a={...e,activeLoadCase:t??null,activeResultStateId:r?.id??null},o=gt(a,t),s=o.find(t=>t.id===e.activeGeometryStateId)??(i?.purpose?o.find(e=>e.purpose===i.purpose):null)??o[0]??null;return{...a,activeGeometryStateId:s?.id??null,visualDeformationScale:s?.purpose===`visualization`&&s.visualScale!=null?Number(s.visualScale):e.visualDeformationScale}}function Ut(e,t){let n=ft(e).find(e=>e.id===t);return n?{...Ht({...e,activeResultStateId:n.id},n.loadCase),visualDeformationScale:e.visualDeformationScale}:{...e,activeResultStateId:t??null,activeLoadCase:n?.loadCase??e.activeLoadCase??null}}function Wt(e,t){let n=gt(e).find(e=>e.id===t);return t&&!n?e:{...e,activeGeometryStateId:t??null,visualDeformationScale:n?.purpose===`visualization`&&n.visualScale!=null?Number(n.visualScale):e.visualDeformationScale}}function Gt(e,t){return{...e,resultThreshold:Math.max(Number(t)||0,0)}}function Kt(e,t){return{...e,utilizationThreshold:Math.max(Number(t)||0,0)}}function qt(e){let t=Et(e);return t?.fieldId??t?.overlay?.id??null}function Jt(e,t){return qt(e)?{...e,legendBands:rt(t)}:e}function Yt(e,t){let n=qt(e);if(!n)return e;let r={...e.legendRanges??{}},i=Number(t?.min),a=Number(t?.max);return Number.isFinite(i)&&Number.isFinite(a)&&a>i?r[n]={min:i,max:a}:delete r[n],{...e,legendRanges:r}}function Xt(e){let t=qt(e);if(!t)return e;let n={...e.legendRanges??{}};return delete n[t],{...e,legendBands:0,legendRanges:n}}function Zt(e,t){return{...e,activeFindingObjectId:t??null}}function Qt(e,t,n){let r=Math.max(Number(n)||0,0);return{...e,resultVectorScales:{...e.resultVectorScales??{},[t]:r}}}function $t(e,t){let n=gt(e).filter(e=>e.purpose===`visualization`),r=n.find(t=>t.overlay.data?.result_state_id===e.activeResultStateId)??n.find(t=>t.id===e.activeGeometryStateId)??n[0];return{...e,activeGeometryStateId:r?.id??e.activeGeometryStateId,visualDeformationScale:Math.max(Number(t)||0,0)}}function en(e){return(e.overlays??[]).filter(e=>e.kind===`solver_result`)}function tn(e){return nn(e).length>0}function nn(e){return Object.values(e??{}).map(Number).filter(e=>Number.isFinite(e))}function rn(e){let t=Number(e);return Number.isFinite(t)&&t>0?t:null}function an(e,t,n){let r=e>>16&255,i=e>>8&255,a=e&255,o=t>>16&255,s=t>>8&255,c=t&255,l=Math.round(r+(o-r)*n),u=Math.round(i+(s-i)*n),d=Math.round(a+(c-a)*n);return(l<<16)+(u<<8)+d}var on={open:`○`,sticking:`■`,sliding:`➜`,indeterminate:`?`},sn={open:6583435,sticking:2450411,sliding:1013358,indeterminate:9584654},cn=e=>Array.isArray(e)&&e.length===3&&e.every(Number.isFinite)?Math.hypot(...e):NaN,ln=(e,t)=>e.reduce((e,n,r)=>e+n*t[r],0),un=(e,t)=>[e[1]*t[2]-e[2]*t[1],e[2]*t[0]-e[0]*t[2],e[0]*t[1]-e[1]*t[0]],dn={slip:`slid on its friction cone`,lift_off:`lifted clear`,reseat:`reseated`,force_reversal:`reversed its tangential force`,over_limit:`reported friction beyond its cone`,unloaded:`carried no normal force`},fn=[`lift_off`,`over_limit`,`slip`,`unloaded`,`force_reversal`,`reseat`];function pn(e){return e.status===`indeterminate`&&e.normal_force>1&&e.friction_limit===0?`closed (frictionless)`:e.status}function mn(e){let t=vt(e)?.overlay.data?.contact_results??{};return Object.fromEntries(Object.entries(t).filter(([,e])=>e&&on[e.status]&&typeof e.support_id==`string`&&[e.normal,e.tangential_force,e.relative_displacement,e.slip].every(e=>Number.isFinite(cn(e)))&&cn(e.normal)>0&&[e.normal_force,e.friction_limit,e.gap].every(Number.isFinite)&&(e.utilization===null||Number.isFinite(e.utilization))))}function hn(e,t){return _(e,`support:${t}`)??(e.objects??[]).find(e=>e.metadata?.support_id===t||e.id===t)?.id??null}function gn(e){let t=vt(e)?.overlay.data??{},n=t.metadata?.run_id??t.metadata?.analysis_id??t.load_case;return ft(e).filter(({overlay:e})=>{let t=e.data??{};return(t.metadata?.run_id??t.metadata?.analysis_id??t.load_case)===n})}function _n(e){let t=cn(e);if(!(t>0))return null;let n=e.map(e=>e/t),r=Math.abs(n[0])<.9?[1,0,0]:[0,1,0],i=ln(r,n),a=r.map((e,t)=>e-i*n[t]),o=cn(a);return[a.map(e=>e/o),un(n,a).map(e=>e/o)]}function vn(e,t,n=`t1`){let r=gn(e),i=_n(r.find(e=>e.overlay.data?.contact_results?.[t])?.overlay.data?.contact_results?.[t]?.normal);return r.map((e,r)=>{let a=e.overlay.data,o=a?.contact_results?.[t],s=i?.[+(n===`t2`)],c=o&&s&&Number.isFinite(cn(o.relative_displacement))&&Number.isFinite(cn(o.tangential_force))&&Number.isFinite(o.friction_limit)&&Number.isFinite(o.normal_force);return{id:e.id,index:r,label:a?.metadata?.stage_label??e.label,pseudoTime:a?.metadata?.pseudo_time,contact:o,available:!!c,travel:c?ln(o.relative_displacement,s):null,force:c?ln(o.tangential_force,s):null}})}function yn(e){let t=(e.resultStates??[]).flatMap(e=>Object.values(e.data?.contact_results??{}));return{normal:Math.max(0,...t.map(e=>e.normal_force).filter(Number.isFinite)),tangential:Math.max(0,...t.map(e=>cn(e.tangential_force)).filter(Number.isFinite))}}function bn(e,t){let n=(e,n)=>N(e,n,t)||`unavailable`,r=dn[e.kind]??e.kind.replaceAll(`_`,` `),i=e.support_ids?.join(`, `)??`the shoe`,a=e.spans_stages?`from ${e.stage_label} through ${e.final_stage_label}`:`at ${e.stage_label}`,o=e.values??{},s=[];if(Number.isFinite(o.tangential_force_n)){let e=Number.isFinite(o.friction_limit_n)?` against a ${n(o.friction_limit_n,`N`)} cone`:``;s.push(`${n(o.tangential_force_n,`N`)} tangential${e}`)}return Number.isFinite(o.slip_m)&&o.slip_m>0&&s.push(`${n(o.slip_m,`m`)} slip`),Number.isFinite(o.gap_m)&&o.gap_m>0&&s.push(`clear by ${n(o.gap_m,`m`)}`),Number.isFinite(o.normal_force_n)&&s.push(`${n(o.normal_force_n,`N`)} normal`),`${i} ${r} ${a}${s.length?` — ${s.join(`, `)}`:``}.`}function xn(e){let t=e.contactFindings?.primary??null;if(!t)return null;let n=O(e),r=[...t.findings??[]].sort((e,t)=>e.stage_index-t.stage_index||fn.indexOf(e.kind)-fn.indexOf(t.kind)||(e.support_ids??[]).join().localeCompare((t.support_ids??[]).join())),i=(t.shoes??[]).filter(e=>e.frictionless),a=(t.shoes??[]).filter(e=>!e.frictionless),o=[];if(r.length)for(let e of r){let t=document.createElement(`li`);t.className=`contact-finding contact-finding-${e.severity}`,t.dataset.stageIndex=String(e.stage_index),t.dataset.kind=e.kind,t.dataset.severity=e.severity,t.dataset.focusKey=`contact-finding:${e.id}`,t.textContent=bn(e,n),o.push(t)}else if(a.length===0){let e=document.createElement(`li`);e.className=`contact-finding`,e.textContent=`No shoe has a friction coefficient, so none of the ${t.shoe_count??0} shoes in this run carries a Coulomb cone. There is no friction to review here - it is a comparison, not a demonstration.`,o.push(e)}else{let e=document.createElement(`li`);e.className=`contact-finding`,e.textContent=`No shoe moved across the ${t.stage_count} published stages: every one of the ${a.length} shoes with a friction coefficient stayed seated and stuck.`,o.push(e)}for(let e of i){if(!e.note)continue;let t=document.createElement(`li`);t.className=`contact-finding contact-finding-frictionless`,t.dataset.kind=`frictionless`,t.dataset.supportId=e.support_id,t.dataset.focusKey=`contact-frictionless:${e.support_id}`,t.textContent=`${e.support_id}: ${e.note}`,o.push(t)}return{findings:r,lines:o,frictionless:i}}function Sn(e,t,n){let r=pt(e);if(r.length<2)return null;let i=mt(e),a=document.createElement(`div`);a.className=`contact-step-nav`,a.setAttribute(`role`,`group`),a.setAttribute(`aria-label`,`Load path stages`);let o=e=>{t({type:`setActiveResultState`,resultStateId:e}),n()};for(let e of r){let t=document.createElement(`button`);t.type=`button`,t.textContent=e.label,t.dataset.focusKey=`contact-stage:${e.index}`,t.dataset.stageIndex=String(e.index),t.setAttribute(`aria-pressed`,String(e.index===i)),t.title=`${e.label} — ${e.incrementCount} converged increments`;let n=e.findings.filter(e=>e.severity===`attention`);t.dataset.hasFinding=String(n.length>0),t.classList.toggle(`is-active`,e.index===i),t.onclick=()=>o(e.resultStateId),a.append(t)}return{nav:a,steps:wn(`Increment`,Cn(e,r,o))}}function Cn(e,t,n){let r=document.createElement(`div`);r.className=`contact-increment`;let i=mt(e),a=t.find(e=>e.index===i)??t[0],o=vt(e)?.id,s=Math.max(0,a.resultStateIds.indexOf(o)),c=document.createElement(`input`);c.type=`range`,c.min=`0`,c.max=String(Math.max(0,a.resultStateIds.length-1)),c.value=String(s),c.disabled=a.resultStateIds.length<2,c.dataset.focusKey=`contact-increment`,c.setAttribute(`aria-label`,`Converged increment within ${a.label}`),c.oninput=()=>{let t=a.resultStateIds[Number(c.value)];t&&t!==e.activeResultStateId&&n(t)};let l=document.createElement(`span`);return l.className=`contact-increment-readout`,l.textContent=`${s+1} / ${a.resultStateIds.length}`,r.append(c,l),r}function wn(e,t){let n=document.createElement(`div`);n.className=`contact-nav-row`;let r=document.createElement(`span`);return r.className=`contact-nav-label`,r.textContent=e,n.append(r,t),n}function Tn(e,t,n,r=`table`,i=null){if(!(e.resultStates??[]).some(e=>Object.keys(e.data?.contact_results??{}).length))return null;let a=document.createElement(`section`);a.className=`contact-review`,a.setAttribute(`aria-label`,`Contact review`);let o=(e,t,n=a)=>{let r=document.createElement(e);return r.textContent=t,n.append(r),r},s=e=>{t(e),n()},c=vt(e)?.overlay.data;if(r===`display`){for(let[t,n]of[[`normal`,`Normal-force arrows`],[`tangential`,`Tangential-force arrows`]]){let r=o(`label`,n),i=document.createElement(`input`);i.type=`checkbox`,i.dataset.focusKey=`contact-arrow:${t}`,i.checked=e.contactArrows?.[t]!==!1,i.onchange=()=>s({type:`setContactArrows`,quantity:t,visible:i.checked}),r.prepend(i)}let t=o(`label`,`Neutral pipe colouring (contact review)`),n=document.createElement(`input`);return n.type=`checkbox`,n.checked=e.contactNeutral!==!1,n.dataset.focusKey=`contact-neutral`,n.onchange=()=>s({type:`setContactNeutral`,neutral:n.checked}),t.prepend(n),a}let l=Object.values(mn(e)),u=l.find(t=>hn(e,t.support_id)===i),d=O(e),f=(e,t)=>N(e,t,d)||`unavailable`;if(r===`selection`){if(!u)return null;o(`h3`,`Selected shoe ${u.support_id}`),o(`p`,`Relative displacement: ${u.relative_displacement.map(e=>f(e,`m`)).join(`, `)} (global X, Y, Z).`);let t=o(`select`,``,o(`label`,`History axis `));for(let[e,n]of[[`t1`,`Tangential t1`],[`t2`,`Tangential t2`],[`normal`,`Normal load vs step`]]){let r=o(`option`,n,t);r.value=e}return t.dataset.focusKey=`contact-history-axis`,t.value=e.contactHistoryAxis??`t1`,t.onchange=()=>s({type:`setContactHistoryAxis`,axis:t.value}),a.append(kn(e,u.support_id)),o(`p`,`t1 = projected global X (Y if near parallel to the normal); t2 = normal × t1. Signed travel is relative displacement, not accumulated slip. The projected force plot is not the full vector friction cone. Dashed lines: ±μN.`),a}o(`h2`,`Contact forces on the pipe`),o(`p`,`Gap, slip and travel are true values. Deformation shown \u00d7${e.visualDeformationScale??1}.`);let p=xn(e);if(p){let e=o(`ol`,``,a);e.className=`contact-findings`,e.append(...p.lines)}if(!l.length)return o(`p`,`Contact results unavailable for this state.`),a;let m=pt(e),h=e.contactFindings?.primary?.shoes??[],g=e.contactFindings?.over_limit_utilization??1.0001,_=m.length>1&&h.length>0,v=o(`div`,``,a);_&&(v.className=`contact-table-scroll contact-strip-wrap`),v.tabIndex=0,v.setAttribute(`role`,`region`),v.setAttribute(`aria-label`,_?`Contact results, with one column per load path stage, scrolls sideways`:`Contact results, scrolls sideways`);let y=o(`table`,``,v);_&&(y.className=`contact-strip`);let b=o(`tr`,``,o(`thead`,``,y));for(let e of[`Support`,`State`,`N`,`|Ft|`,`μN`,`Usage`,`Gap`,`|Slip|`])o(`th`,e,b).scope=`col`;for(let e of m){let t=o(`th`,e.label,b);t.scope=`col`,t.className=`contact-strip-head`,t.title=`${e.label} — ${e.incrementCount} converged increments`}let x=o(`tbody`,``,y),S=mt(e);for(let t of l){let n=o(`tr`,``,x);n.dataset.selected=String((e.selectedObjectIds??[]).includes(hn(e,t.support_id)));let r=o(`td`,``,n),i=o(`button`,t.support_id,r);i.type=`button`,i.dataset.focusKey=`contact-support:${t.support_id}`;let a=hn(e,t.support_id);i.disabled=!a,i.onclick=e=>s({type:`selectObject`,objectId:a,additive:e.shiftKey});for(let e of[`${on[t.status]??`?`} ${pn(t)} (${t.status_source})`,f(t.normal_force,`N`),f(cn(t.tangential_force),`N`),f(t.friction_limit,`N`),t.utilization==null?`n/a`:`${(100*t.utilization).toFixed(1)}%`,f(t.gap,`m`),f(cn(t.slip),`m`)])o(`td`,e,n);let c=h.find(e=>e.support_id===t.support_id)??null;for(let e of m){let r=c?.stages?.find(t=>t.index===e.index)??null,i=o(`td`,``,n);i.className=`contact-strip-cell`,i.dataset.stageIndex=String(e.index);let a=r?.governing_status??r?.status;i.dataset.status=a??`unknown`,e.index===S&&i.classList.add(`is-active`),r?.transitioned&&(i.dataset.transitioned=`true`),i.textContent=on[a]??`·`;let s=r?.peak_utilization;i.title=En(t.support_id,e,r,d,f),s!=null&&s>g&&i.classList.add(`is-over-limit`)}t.utilization>g&&n.classList.add(`contact-limit-exceeded`)}let C=On(e);C&&(o(`h3`,`All shoes: force against travel`),a.append(C),o(`p`,`One line per shoe, solid, with its own dashed ±μN cone. Filled ring marks the increment on screen. The projected component, not the full friction cone.`));let w=o(`details`,``);o(`summary`,`Contact provenance`,w);for(let e of[`run_id`,`analysis_id`,`source`,`runtime_version`,`code_aster_version`,`formulation`,`convergence_status`,`contact_status_tolerances`,`contact_variable_mapping`,`native_contact_status`,`contact_status_basis`]){let t=c?.metadata?.[e];t!=null&&o(`p`,`${e}: ${typeof t==`object`?JSON.stringify(t):t}`,w)}return a}function En(e,t,n,r,i){if(!n)return`${e}: no contact result in ${t.label}`;let a=[`${e} at ${t.label}`],o=n.statuses??[n.status];return a.push(o.length>1?o.join(` then `):n.status),n.transitioned&&n.status!==n.governing_status&&a.push(`ended on ${n.status}`),n.peak_normal_force_n>0&&a.push(`peak N ${i(n.peak_normal_force_n,`N`)}`),n.peak_tangential_force_n>0&&a.push(`peak |Ft| ${i(n.peak_tangential_force_n,`N`)}`),n.peak_utilization!=null&&a.push(`${(100*n.peak_utilization).toFixed(1)}% of cone`),n.peak_gap_m>0&&a.push(`clear ${i(n.peak_gap_m,`m`)}`),n.peak_slip_m>0&&a.push(`slip ${i(n.peak_slip_m,`m`)}`),a.join(` · `)}var Dn=[`#2563eb`,`#0f766e`,`#b45309`,`#7c3aed`,`#be123c`,`#4d7c0f`];function On(e){let t=e.contactFindings?.primary?.shoes??[];if(t.length<2)return null;let n=e.contactHistoryAxis??`t1`,r=O(e),i=t.map((t,r)=>({shoe:t,color:Dn[r%Dn.length],points:vn(e,t.support_id,n).filter(e=>e.available)})).filter(e=>e.points.length>0);if(i.length<2)return null;let a=e=>M(e.travel,`m`,r),o=e=>M(e.force,`N`,r),s=e=>M(e.contact.friction_limit,`N`,r),c=i.flatMap(e=>e.points),l=Math.max(0,...c.map(a))-Math.min(0,...c.map(a)),u=Math.min(0,...c.map(a)),d=Math.abs(u)<l*.001?0:u,f=Math.max(0,...c.map(a)),p=Math.max(1e-9,...c.map(e=>Math.max(Math.abs(o(e)),s(e)))),m=e=>54+(e-d)/(f-d||1)*392,h=e=>105-e/p*85,g=232+i.length*14,_=`http://www.w3.org/2000/svg`,v=document.createElementNS(_,`svg`);v.setAttribute(`viewBox`,`0 0 460 ${g}`),v.setAttribute(`role`,`img`);let y=i.map(e=>e.shoe.support_id).join(`, `);v.setAttribute(`aria-label`,`Solved force against travel for ${y}, with each shoe's Coulomb envelope`);let b=(e,t,n)=>{let r=document.createElementNS(_,e);for(let[e,n]of Object.entries(t))r.setAttribute(e,n);return n&&(r.textContent=n),v.append(r),r};b(`path`,{d:`M54 20V190H446 M54 105H446`,stroke:`#64748b`,fill:`none`});for(let t of i){let n=e=>{let n=!1;return t.points.map(t=>{let r=`${n?`L`:`M`}${m(a(t)).toFixed(2)},${h(e(t)).toFixed(2)}`;return n=!0,r}).join(` `)};for(let[e,r,i]of[[s,`5 4`,.45],[e=>-s(e),`5 4`,.45],[o,null,1]]){let a={d:n(e),stroke:t.color,"stroke-width":r?1.5:2,opacity:i,fill:`none`};r&&(a[`stroke-dasharray`]=r),b(`path`,a)}for(let e of t.points){let n=b(`circle`,{cx:m(a(e)),cy:h(o(e)),r:2,fill:t.color}),i=document.createElementNS(_,`title`);i.textContent=`${t.shoe.support_id} · ${e.label} · ${N(e.force,`N`,r)}`,n.append(i)}let i=t.points.find(t=>t.id===e.activeResultStateId);i&&b(`circle`,{cx:m(a(i)),cy:h(o(i)),r:4.5,fill:t.color,stroke:`#0b1220`})}return b(`text`,{x:54,y:14,"font-size":11},`Force on pipe [${j(`N`,r)}], range ±${Number(p.toPrecision(4))}`),b(`text`,{x:54,y:206,"font-size":11},`${n===`normal`?`Converged step`:`Signed ${n} travel [${j(`m`,r)}]`}: ${Number(d.toPrecision(4))} … ${Number(f.toPrecision(4))}`),i.forEach((e,t)=>{let n=220+t*14;b(`rect`,{x:54,y:n-7,width:10,height:3,fill:e.color});let i=e.shoe.frictionless?`${N(e.shoe.peak_tangential_force_n,`N`,r)} peak, no cone (μ = 0)`:`${N(e.shoe.peak_tangential_force_n,`N`,r)} peak, ${(100*(e.shoe.peak_utilization??0)).toFixed(0)}% of cone`;b(`text`,{x:70,y:n,"font-size":10},`${e.shoe.support_id} — ${on[e.shoe.final_status]??``} ${i}`)}),v}function kn(e,t){let n=`http://www.w3.org/2000/svg`,r=document.createElementNS(n,`svg`);r.setAttribute(`viewBox`,`0 0 420 230`),r.setAttribute(`role`,`img`),r.setAttribute(`aria-label`,`${t} solved contact history with current step and Coulomb envelope`);let i=e.contactHistoryAxis??`t1`,a=vn(e,t,i),o=a.filter(e=>e.available),s=O(e),c=e=>i===`normal`?e.index:M(e.travel,`m`,s),l=e=>M(i===`normal`?e.contact.normal_force:e.force,`N`,s),u=e=>M(e.contact.friction_limit,`N`,s),d=Math.min(0,...o.map(c)),f=Math.max(0,...o.map(c)),p=Math.max(1e-9,...o.map(e=>Math.max(Math.abs(l(e)),i===`normal`?0:u(e)))),m=e=>54+(e-d)/(f-d||1)*345,h=e=>108-e/p*80,g=(e,t,i)=>{let a=document.createElementNS(n,e);for(let[e,n]of Object.entries(t))a.setAttribute(e,n);return i&&(a.textContent=i),r.append(a),a};g(`path`,{d:`M54 20V190H400 M54 108H400`,stroke:`#64748b`,fill:`none`});for(let[e,t,n]of[[l,`#0f766e`,``],...i===`normal`?[]:[[u,`#64748b`,`5 4`],[e=>-u(e),`#64748b`,`5 4`]]]){let r=!1;g(`path`,{d:a.map(t=>{if(!t.available)return r=!1,``;let n=`${r?`L`:`M`}${m(c(t))},${h(e(t))}`;return r=!0,n}).join(` `),stroke:t,"stroke-width":2,"stroke-dasharray":n,fill:`none`})}for(let e of o){let t=g(`circle`,{cx:m(c(e)),cy:h(l(e)),r:2,fill:`#0f766e`}),r=document.createElementNS(n,`title`);r.textContent=`${e.label} / pseudo-time ${ut(e.pseudoTime)}`,t.append(r)}let _=o.find(t=>t.id===e.activeResultStateId);return _&&g(`circle`,{cx:m(c(_)),cy:h(l(_)),r:5,fill:`#1e293b`}),g(`text`,{x:54,y:14,"font-size":11},`${i===`normal`?`N`:`Ft ${i}`} [${j(`N`,s)}], ±${Number(p.toPrecision(4))}`),g(`text`,{x:54,y:209,"font-size":11},`${i===`normal`?`Converged step`:`Signed ${i} travel [${j(`m`,s)}]`}: ${Number(d.toPrecision(4))} … ${Number(f.toPrecision(4))}`),g(`text`,{x:54,y:225,"font-size":10},_?`${_.label} · pseudo-time ${ut(_.pseudoTime)}`:`Current contact data unavailable`),r}var An=Object.freeze({restraint:`#262626`,spring:`#262626`,prescribed:`#262626`}),jn=Object.freeze({restraint:`Restraint — authored input, solid cones on the held degrees of freedom`,spring:`Support spring — authored input, rings at the support`,prescribed:`Prescribed displacement — authored input, hollow cone, penalty stiffness`});Object.freeze({restraint:`solid`,spring:`solid`,prescribed:`hollow`});var Mn=Object.freeze([`restraint`,`spring`,`prescribed`]);function Nn(e){let t=[],n=Array.isArray(e?.dof_states)?e.dof_states.map(String):[];n.some(e=>e===`fixed`||e===`one-way`)&&t.push(`restraint`);let r=(Array.isArray(e?.stiffness_matrix)?e.stiffness_matrix:[]).map(Number),i=Number(e?.stiffness),a=r.some(e=>Number.isFinite(e)&&Math.abs(e)>0)||r.length===0&&Number.isFinite(i)&&Math.abs(i)>0||Array.isArray(e?.spring_stiffness)&&e.spring_stiffness.some(e=>Number(e)!==0);return(n.some(e=>e===`spring`)||a)&&t.push(`spring`),(Array.isArray(e?.imposed_displacement)?e.imposed_displacement:null)?.some(e=>Math.abs(Number(e))>0)&&t.push(`prescribed`),t}function Pn(e,t){let n=new Set;for(let r of e.objects??[]){if(r.kind!==`support`||!t.has(r.id))continue;let i=e.geometryAssets.find(e=>e.id===r.geometry_asset_id)?.generation_config;for(let e of Nn(i))n.add(e)}return Mn.filter(e=>n.has(e))}var Fn=`engineering_review.v1`,In=/^[a-z0-9][a-z0-9_-]*$/,Ln=class extends Error{};function Rn(e){if(!Hn(e))throw new Ln(`Engineering review must be a JSON object.`);if(e.schema_version!==Fn)throw new Ln(`Engineering review schema_version must be ${Fn}.`);if(typeof e.analysis_status!=`string`||e.analysis_status.length===0)throw new Ln(`Engineering review analysis_status must be a non-empty string.`);if(!Hn(e.tables))throw new Ln(`Engineering review tables must be a JSON object mapping.`);let t=Object.entries(e.tables);for(let[e,n]of t){if(!In.test(e))throw new Ln(`Engineering review table id ${e} must be a stable portable identifier.`);if(!Hn(n))throw new Ln(`Engineering review table ${e} must be a JSON object.`);Bn(e,n)}return{...e,tables:Object.fromEntries(t),tableOrder:t.map(([e])=>e)}}async function zn(e=`.`,t=globalThis.fetch){let n=`${String(e).replace(/\/+$/,``)}/review.json`;try{let e=await t(n);if(e.status===404)return{review:null,diagnostics:[],legacy:!0};if(!e.ok)throw Error(`HTTP ${e.status}${e.statusText?` ${e.statusText}`:``}`);return{review:Rn(await e.json()),diagnostics:[],legacy:!1}}catch(e){return{review:null,diagnostics:[Un(e)],legacy:!1}}}function Bn(e,t){if(t.id!==e)throw new Ln(`Engineering review table ${e} must declare the same stable id.`);for(let n of[`title`,`source`])if(typeof t[n]!=`string`||t[n].length===0)throw new Ln(`Engineering review table ${e} ${n} must be a non-empty string.`);if(!Array.isArray(t.columns))throw new Ln(`Engineering review table ${e} columns must be an array.`);let n=new Set;for(let[r,i]of t.columns.entries()){if(!Hn(i))throw new Ln(`Engineering review table ${e} column ${r} must be a JSON object.`);if(typeof i.id!=`string`||i.id.length===0)throw new Ln(`Engineering review table ${e} column ${r} id must be a non-empty string.`);if(n.has(i.id))throw new Ln(`Engineering review table ${e} has duplicate column id ${i.id}.`);if(n.add(i.id),typeof i.label!=`string`||i.label.length===0)throw new Ln(`Engineering review table ${e} column ${i.id} label must be a non-empty string.`);for(let t of[`unit`,`description`])if(t in i&&typeof i[t]!=`string`)throw new Ln(`Engineering review table ${e} column ${i.id} ${t} must be a string.`)}if(!Array.isArray(t.rows))throw new Ln(`Engineering review table ${e} rows must be an array.`);for(let[n,r]of t.rows.entries()){if(!Hn(r))throw new Ln(`Engineering review table ${e} row ${n} must be a JSON object.`);Vn(r,`Engineering review table ${e} row ${n}`)}}function Vn(e,t){if(!(e===null||typeof e==`string`||typeof e==`boolean`)){if(typeof e==`number`){if(!Number.isFinite(e))throw new Ln(`${t} contains a non-finite number.`);return}if(Array.isArray(e)){e.forEach((e,n)=>Vn(e,`${t}[${n}]`));return}if(Hn(e)){for(let[n,r]of Object.entries(e))Vn(r,`${t}.${n}`);return}throw new Ln(`${t} contains a non-JSON value.`)}}function Hn(e){if(typeof e!=`object`||!e||Array.isArray(e))return!1;let t=Object.getPrototypeOf(e);return t===Object.prototype||t===null}function Un(e){return{severity:`error`,code:e instanceof Ln?`viewer.review.invalid_contract`:`viewer.review.load_failed`,source:`review.json`,message:String(e)}}function Wn(e,t=[]){return e||t[0]||`.`}function Gn(e){if(!e||typeof e!=`object`||!Array.isArray(e.runs))return null;let t=e.runs.filter(e=>e&&typeof e==`object`&&Array.isArray(e.stages)&&Array.isArray(e.shoes)).map(e=>({...e,stages:e.stages.filter(e=>e&&typeof e.result_state_id==`string`),shoes:e.shoes.filter(e=>e&&typeof e.support_id==`string`),findings:Array.isArray(e.findings)?e.findings:[]})).filter(e=>e.stages.length>0);if(t.length===0)return null;let n=t.find(t=>t.run_id===e.primary_run_id)??t.reduce((e,t)=>t.stages.length>e.stages.length?t:e,t[0]);return{...e,runs:t,primary:n}}async function Kn(e=`.`,t=globalThis.fetch){let n=String(e).replace(/\/+$/,``),r=async e=>{let r=`${n}/${e}`,i=await t(r);if(!i.ok)throw Error(`Failed to load ${e}: ${i.status} ${i.statusText}`);let a=i.headers?.get?.(`content-type`)??``;if(a.toLowerCase().includes(`text/html`))throw Error(`Expected JSON from ${r}, but received ${a.split(`;`)[0]}. The bundle URL points to a different application or server.`);return i.json()},i=await r(`scene.json`),a=Array.isArray(i.objects)?i.objects:await r(`metadata/objects.json`),o=await r(`metadata/object_map.json`),s=Array.isArray(i.overlays)?i.overlays:await r(`metadata/overlays.json`),c=Array.isArray(i.geometry_assets)?i.geometry_assets:await r(`geometry/geometry_assets.json`),l=await qn(i.geometry_assets??c,r),u=await zn(n,t);return{scene:i,objects:a,objectMap:o,overlays:s,geometryAssets:c,geometryPayloads:l,review:u.review,reviewDiagnostics:u.diagnostics,legacyReview:u.legacy}}async function qn(e,t){let n=e.map(Jn),r=e.map((e,t)=>({asset:e,index:t})).filter(({asset:e},t)=>!n[t]&&e.uri);for(let e=0;e<r.length;e+=16){let i=r.slice(e,e+16),a=await Promise.all(i.map(({asset:e})=>t(e.uri)));i.forEach(({index:e},t)=>{n[e]=a[t]})}return n.filter(Boolean)}function Jn(e){return!e.format||!e.generation_config||e.format===`tuyau_subpoint_glyphs`?null:{asset_id:e.id,format:e.format,bounds:e.bounds,object_ids:e.object_ids,generation_config:e.generation_config,...e.hash?{hash:e.hash}:{}}}function Yn(e){let t=e.scene,n=t.objects?.length?t.objects:e.objects??[],r=new Set(n.filter(e=>Number(e.physical?.insulation_thickness_m)>0).map(e=>e.entity_ref)),i=n.filter(e=>e.kind===`physical_envelope`?e.metadata?.envelope_type===`insulation`:e.kind===`deformed_envelope`?r.has(e.metadata?.entity_ref):!0),a=t.geometry_assets?.length?t.geometry_assets:e.geometryAssets??[],o=(t.overlays?.length?t.overlays:e.overlays??[]).filter(e=>e.kind!==`physical_envelope`||e.object_ids?.some(e=>i.some(t=>t.id===e))),s=Object.fromEntries(i.map(e=>[e.id,tr(e)])),c=er(i,o,s,(Array.isArray(t.layers)?t.layers:[]).filter(e=>![`physical_envelope:bare_pipe`,`physical_envelope:wind`,`physical_envelope:clearance`,`overlay:physical_envelope`].includes(e.id))),l=o.filter(e=>e.kind===`result_state`),u=o.filter(e=>e.kind===`geometry_state`),d=l[0]??null,f=d?.data?.load_case??u[0]?.data?.load_case??o.find(e=>e.kind===`load_case`)?.data?.load_case??null,p=u.find(e=>e.data?.purpose===`engineering`&&(!f||e.data?.load_case===f))??u.find(e=>!f||e.data?.load_case===f)??u[0]??null,m={sceneId:t.scene_id,reviewFocus:t.review_focus??null,contactFindings:Gn(t.contact_findings),objects:i,objectMap:e.objectMap??{},geometryAssets:a,geometryPayloads:e.geometryPayloads??[],overlays:o,issues:t.issues??[],review:e.review??null,reviewDiagnostics:e.reviewDiagnostics??[],legacyReview:e.legacyReview??!1,views:t.views??[],diagnostics:[...t.diagnostics??[],...ir(i,a,o)],layers:c,objectLayerIds:s,bounds:Qn(a.map(e=>e.bounds)),camera:{mode:`orbit`,target:[0,0,0],distance:1},selectedObjectIds:[],hiddenObjectIds:[],isolatedObjectIds:[],activeIssueId:null,activeOverlayIds:[],stage:`review`,resultStates:l,geometryStates:u,resultFields:Array.isArray(t.result_fields)?t.result_fields:[],activeLoadCase:f,activeResultStateId:d?.data?.id??d?.id??null,activeGeometryStateId:p?.data?.id??p?.id??null,resultThreshold:null,resultVectorScales:{displacement:1,reaction:1,moment:1},utilizationThreshold:null,visualDeformationScale:Number(p?.data?.visual_scale??p?.data?.displacement_scale??1),modelColorBy:`default`,visibleOverlayIds:o.filter(e=>e.visible!==!1).map(e=>e.id),visibleObjectIds:[]},h={...m,colorChannel:Be(m)};return{...h,coloring:Oe(h),visibleObjectIds:Zn(h)}}function Xn(e,t,n){let r={...e.layers,[t]:{...e.layers[t],visible:n}},i=e.overlays,a=r[t];a?.source===`overlay`&&(i=e.overlays.map(e=>e.kind===a.overlayKind?{...e,visible:n}:e));let o={...e,layers:r,overlays:i,visibleOverlayIds:i.filter(e=>e.visible!==!1).map(e=>e.id)};return{...o,visibleObjectIds:Zn(o)}}function Zn(e){let t=new Set(e.hiddenObjectIds??[]),n=new Set(e.isolatedObjectIds??[]),r=$n(e),i=Ge(e)!==`build`&&bt(e);return e.objects.filter(t=>!e.activeLoadCase||!t.metadata?.load_case||t.metadata.load_case===e.activeLoadCase).filter(t=>!e.activeResultStateId||!t.metadata?.result_state_id||t.metadata.result_state_id===e.activeResultStateId).filter(t=>!e.activeGeometryStateId||!t.metadata?.geometry_state_id||t.metadata.geometry_state_id===e.activeGeometryStateId).filter(e=>!i||![`applied_load`,`displacement_vector`,`reaction_vector`].includes(e.kind)).filter(t=>nr(e,t)).filter(e=>!t.has(e.id)).filter(e=>!r.has(e.id)).filter(e=>n.size===0||n.has(e.id)).filter(t=>rr(e,t.id)).map(e=>e.id)}function Qn(e){let t=e.filter(e=>Array.isArray(e)&&e.length===6);if(t.length===0)return[0,0,0,0,0,0];let n=[1/0,1/0,1/0],r=[-1/0,-1/0,-1/0];for(let e of t)for(let t=0;t<3;t+=1)n[t]=Math.min(n[t],e[t]),r[t]=Math.max(r[t],e[t+3]);return[...n,...r]}function $n(e){let t=new Set,n=new Set([`physical_envelope`,`clash_marker`,`rule_marker`,`route_candidate`,`displacement_vector`,`reaction_vector`]);for(let r of e.overlays??[])if(r.visible===!1)for(let i of r.object_ids??[]){let r=e.objects.find(e=>e.id===i);r&&n.has(r.kind)&&t.add(i)}return t}function er(e,t,n,r=[]){let i=new Map(r.map(e=>[e.id,e])),a={},o=e=>{let t=i.get(e);return t?{category:t.category,label:t.label||ar(e),meshIdentity:t.mesh_identity}:{}},s=e=>i.get(e)?.default_visible!==!1;for(let t of e)for(let e of n[t.id]??[t.kind||`object`])a[e]??={id:e,label:ar(e),defaultVisible:s(e),visible:s(e),count:0,source:`object`,objectIds:[],...o(e)},a[e].count+=1,a[e].objectIds.push(t.id);for(let e of t){let t=`overlay:${e.kind||`overlay`}`;a[t]??={id:t,label:ar(t),defaultVisible:e.visible!==!1&&s(t),visible:e.visible!==!1&&s(t),count:0,source:`overlay`,overlayKind:e.kind||`overlay`,overlayIds:[],...o(t)},a[t].count+=1,a[t].overlayIds.push(e.id),e.visible===!1&&(a[t].visible=!1)}for(let e of r)a[e.id]??={id:e.id,label:e.label||ar(e.id),defaultVisible:e.default_visible!==!1,visible:e.default_visible!==!1,count:0,source:`scene`,category:e.category,meshIdentity:e.mesh_identity};return a}function tr(e){return Array.isArray(e.layer_ids)&&e.layer_ids.length>0?[...e.layer_ids]:[e.kind||`object`]}function nr(e,t){return(e.objectLayerIds?.[t.id]??tr(t)).every(t=>e.layers[t]?.visible!==!1)}function rr(e,t){if(!e.sectionBox)return!0;let n=e.geometryAssets.find(e=>(e.object_ids??[]).includes(t));if(!n?.bounds||n.bounds.length!==6)return!0;let r=n.bounds,i=e.sectionBox.min,a=e.sectionBox.max;return r[3]>=i[0]&&r[0]<=a[0]&&r[4]>=i[1]&&r[1]<=a[1]&&r[5]>=i[2]&&r[2]<=a[2]}function ir(e,t,n){let r=[],i=new Set(t.map(e=>e.id)),a=new Set(e.map(e=>e.id));for(let t of e)t.geometry_asset_id&&!i.has(t.geometry_asset_id)&&r.push({code:`viewer.missing_geometry_asset`,severity:`warning`,message:`Object ${t.id} references missing geometry asset ${t.geometry_asset_id}.`,object_id:t.id,asset_id:t.geometry_asset_id});for(let e of n)for(let t of e.object_ids??[])a.has(t)||r.push({code:`viewer.overlay_missing_object`,severity:`warning`,message:`Overlay ${e.id} references missing object ${t}.`,overlay_id:e.id,object_id:t});return r}function ar(e){return e.replace(/^overlay:/,`overlay:`).split(/[:_-]+/).map(e=>`${e.slice(0,1).toUpperCase()}${e.slice(1)}`).join(` `)}var or=[{id:`design`,label:`Design`},{id:`analysis_mesh`,label:`Analysis mesh`},{id:`results`,label:`Results`},{id:`annotations`,label:`Annotations`}],sr={geometry:`design`,envelopes:`design`,analysis_mesh:`analysis_mesh`,results:`results`,overlays:`annotations`,other:`annotations`};function cr(e){let t=String(e);return t===`overlay:physical_envelope`?`envelopes`:t===`overlay:solver_result`?`results`:t.startsWith(`overlay:`)?`overlays`:t.startsWith(`analysis_mesh:`)?`analysis_mesh`:t.startsWith(`result:`)||t.startsWith(`solver_result:`)||t.startsWith(`deformed:`)?`results`:t.startsWith(`physical_envelope:`)?`envelopes`:t.includes(`:`)?`other`:`geometry`}function lr(e,t=null){return t&&or.some(e=>e.id===t)?t:sr[cr(e)]??`annotations`}function ur(e){let t=new Map(or.map(e=>[e.id,[]]));for(let n of Object.values(e??{}))t.get(lr(n.id,n.category)).push(n);let n=[];for(let e of or){let r=t.get(e.id);if(r.length===0)continue;let i=r.filter(e=>!dr(e)),a=r.filter(dr);if(i.length===0&&a.length===0)continue;let o=[],s=[];for(let e of i){let t={layerId:e.id,label:e.label||mr(e.id),count:e.count};/:group:[^:]+$/.test(e.id)?s.push(t):o.push(t)}n.push({id:e.id,label:e.label,layerIds:i.map(e=>e.id),leaves:o,groups:s.length>0?[{label:`Groups`,leaves:s}]:[],meshIdentity:a.map(e=>e.meshIdentity).find(Boolean)??null})}return n}function dr(e){return e.source===`scene`&&!e.count}function fr(e,t){let n=Ue(t);if(!n)return e;let r=e;for(let t of ur(e.layers)){if(!(t.id in n))continue;let i=n[t.id];for(let n of t.layerIds)r=Xn(r,n,i&&e.layers[n]?.defaultVisible!==!1)}return r}var pr=Object.freeze({G:`Elements`,GN:`Nodes`,MAT:`Material`,SEC:`Section`});function mr(e){if(e===`support`)return`Supports / constraints`;let t=hr(String(e).split(`:`).at(-1));if(t.length===0)return e;let n=pr[t[0]];if(n&&t.length>1){let e=t.slice(1);return e.at(-1).toLowerCase()===t[0].toLowerCase()&&e.pop(),`${n}: ${gr(e)}`}return gr(t)}function hr(e){return e.replace(/([a-z0-9])([A-Z])/g,`$1 $2`).replace(/([A-Z]+)([A-Z][a-z])/g,`$1 $2`).split(/[\s_-]+/).filter(Boolean)}function gr(e){let[t,...n]=e.map(e=>/\d/.test(e)?e:e.toLowerCase());return t?[`${t.slice(0,1).toUpperCase()}${t.slice(1)}`,...n].join(` `):``}var _r=Object.freeze([1,.6,.3]),vr=.6,yr=Object.freeze([{id:`geometry`,label:`Geometry`,description:`What the engineer authored. Real surface, real wall.`,supportsOpacity:!0},{id:`insulation`,label:`Insulation`,description:`Assigned insulation: included in weight, wind diameter and clearance checks.`,supportsOpacity:!0},{id:`analysis_mesh`,label:`Analysis mesh`,description:`Elements on the centerline. No surface exists - the tube is swept from section properties.`,supportsOpacity:!0},{id:`subpoints`,label:`Sub-points`,description:`Where the stress actually lives. Projected onto the wall at their shell display positions.`,supportsOpacity:!0},{id:`deformed`,label:`Deformed mesh`,description:`A transform of the mesh, not a fourth body - it overlays the undeformed geometry.`,supportsOpacity:!1}]),br=Object.freeze(yr.map(e=>e.id)),xr=Object.freeze([{id:`support`,label:`Supports & BCs`,description:`Restraints and boundary conditions as the solver received them.`,layerIds:[`support`]},{id:`support_link`,label:`Support attachments`,description:`Which structure each attached support acts against. Ground supports carry a hatch instead.`,layerIds:[`support_link`]},{id:`applied_force`,label:`Applied forces`,description:`Nodal forces applied to the model.`,layerIds:[`design:loads:forces`]},{id:`applied_moment`,label:`Applied moments`,description:`Nodal moments applied to the model.`,layerIds:[`design:loads:moments`]},{id:`applied_line_load`,label:`Applied line loads`,description:`Distributed line loads applied along elements.`,layerIds:[`design:loads:line_loads`]},{id:`reaction_force`,label:`Reaction forces`,description:`Reaction forces at the restrained degrees of freedom.`,layerIds:[`result:reaction_force`],vectorType:`reaction`},{id:`reaction_moment`,label:`Reaction moments`,description:`Reaction moments, right-hand rule.`,layerIds:[`result:reaction_moment`],vectorType:`moment`},{id:`displacement`,label:`Displacements`,description:`Nodal displacement vectors.`,layerIds:[`result:displacement`],vectorType:`displacement`},{id:`ground_grid`,label:`Ground grid`,description:`The reference plane under the model. Orientation is on the corner gizmo.`,stateKey:`referenceGridVisible`}]);Object.freeze(xr.map(e=>e.id));var Sr=Object.freeze([.5,1,2,5]);function Cr(e,t){let n=Number(e.resultVectorScales?.[t]);return Number.isFinite(n)?n:1}function wr(e){let t=[];for(let n of xr){if(n.stateKey){t.push({...n,layerIds:[],count:null,visible:e[n.stateKey]!==!1,partiallyVisible:!1,scale:null});continue}let r=n.layerIds.map(t=>e.layers?.[t]).filter(e=>e&&e.count>0);if(r.length===0)continue;let i=r.map(e=>e.visible!==!1);t.push({...n,layerIds:r.map(e=>e.id),count:r.reduce((e,t)=>e+t.count,0),visible:i.every(Boolean),partiallyVisible:!i.every(Boolean)&&i.some(Boolean),scale:n.vectorType?Cr(e,n.vectorType):null})}return t}function Tr(e,t,n){let r=wr(e).find(e=>e.id===t);return r?r.stateKey?{...e,[r.stateKey]:n}:Dr(e,r.layerIds,n):e}function Er(e){return Sr[(Sr.findIndex(t=>Math.abs(t-e)<1e-9)+1)%Sr.length]}function Dr(e,t,n){let r=e;for(let e of t)r=Xn(r,e,n);return r}function Or(e,t=null){let n=String(e);if(n===`physical_envelope:insulation`)return`insulation`;if(n.startsWith(`physical_envelope:`)||n===`overlay:physical_envelope`)return null;if(n.includes(`tuyau_subpoint`))return`subpoints`;if(n.startsWith(`deformed:`))return`deformed`;if(n===`analysis_mesh:helpers`)return null;let r=lr(n,t);return r===`design`?`geometry`:r===`analysis_mesh`?`analysis_mesh`:null}function kr(e){let t=new Map(br.map(e=>[e,[]]));for(let n of Object.values(e.layers??{})){let e=Or(n.id,n.category);e&&t.get(e).push(n)}let n=[];for(let r of yr){let i=t.get(r.id).filter(e=>e.count>0);if(i.length===0)continue;let a=i.map(e=>e.visible!==!1);n.push({...r,layerIds:i.map(e=>e.id),visible:a.every(Boolean),partiallyVisible:!a.every(Boolean)&&a.some(Boolean),opacity:r.supportsOpacity?Nr(e,r.id):1,badge:Hr(e,r.id),metrics:Ur(e,r.id)})}return n}function Ar(e,t,n){let r=kr(e).find(e=>e.id===t);if(!r)return e;let i=Dr(e,r.layerIds,n);if(t===`analysis_mesh`){let e=Nr(i,`geometry`);n&&Math.abs(e-1)<1e-4?i=jr(i,`geometry`,.35):!n&&Math.abs(e-.35)<1e-4&&(i=jr(i,`geometry`,1))}return i}function jr(e,t,n){let r=Number(n);return Number.isFinite(r)?{...e,bodyOpacity:{...e.bodyOpacity??{},[t]:$r(r,0,1)}}:e}function Mr(e,t){let n=Nr(e,t),r=_r[(_r.findIndex(e=>Math.abs(e-n)<1e-9)+1)%_r.length];return jr(e,t,r)}function Nr(e,t){let n=Number(e.bodyOpacity?.[t]);return Number.isFinite(n)?$r(n,0,1):1}function Pr(e){return e.bodyOpacity?e:{...e,bodyOpacity:Fr(e)}}function Fr(e){let t=Object.values(e.layers??{}).some(e=>e.category===`analysis_mesh`&&e.count>0&&e.visible!==!1),n=Object.values(e.layers??{}).some(e=>e.id?.includes(`tuyau_subpoint`)&&e.count>0&&e.visible!==!1);return{geometry:t||n?vr:1,analysis_mesh:1,subpoints:1}}function Ir(e,t=[]){for(let n of t)for(let t of e.objectLayerIds?.[n]??[]){let n=Or(t,e.layers?.[t]?.category);if(yr.find(e=>e.id===n)?.supportsOpacity)return Nr(e,n)}return null}function Lr(e){return Object.values(e.layers??{}).find(e=>e.meshIdentity)?.meshIdentity??null}function Rr(e){return(e.overlays??[]).find(t=>t.data?.result_type===`tuyau_subpoints`&&(!e.activeResultStateId||!t.data?.result_state_id||t.data.result_state_id===e.activeResultStateId))??null}function zr(e){return Rr(e)?.data?.section_profile??null}function Br(e){let t=Rr(e)?.data;if(!t)return null;let n=t.legend?.range??t.range;return!n||!Number.isFinite(Number(n.min))||!Number.isFinite(Number(n.max))?null:{field:t.legend?.field??t.field??`TUYAU sub-point`,unit:t.legend?.unit??t.unit??``,range:{min:Number(n.min),max:Number(n.max)}}}function Vr(e){return Lr(e)?.discretisation??null}function Hr(e,t){if(t===`insulation`)return{text:`physical`,tone:`neutral`};if(t===`geometry`)return{text:`3D solid`,tone:`neutral`};if(t===`analysis_mesh`){let t=Lr(e)?.topological_dim;return Number.isFinite(t)&&t>=0?{text:`${t}D`,tone:`accent`}:{text:`mesh`,tone:`neutral`}}if(t===`subpoints`)return{text:`2.5D`,tone:`accent`};let n=Xr(e)?.data?.state_type;return{text:n?String(n).toUpperCase():`deformed`,tone:`neutral`}}function Ur(e,t){return t===`insulation`?[...new Set((e.objects??[]).flatMap(t=>{let n=t.metadata?.insulation;return n?[`${n.material} · ${N(n.thickness_m,`m`,O(e))}`]:[]}))]:t===`geometry`?Wr(e):t===`analysis_mesh`?Kr(e):t===`subpoints`?qr(e):Jr(e)}function Wr(e){let t=new Set;for(let n of Object.values(e.layers??{}))if(Or(n.id,n.category)===`geometry`)for(let e of n.objectIds??[])t.add(e);let n=(e.objects??[]).filter(e=>t.has(e.id)&&e.geometry_asset_id),r=new Map;for(let e of n){let t=e.kind||`object`;r.set(t,(r.get(t)??0)+1)}let i=[...r.entries()].sort((e,t)=>t[1]-e[1]||e[0].localeCompare(t[0])).slice(0,3).map(([e,t])=>`${t} ${e.replace(/_/g,` `)}`).join(` · `),a=[];i&&a.push(i);let o=Gr(n,O(e));return o&&a.push(o),a}function Gr(e,t){let n=e.map(e=>e.metadata?.profile).find(e=>e?.outer_diameter_m);if(!n)return null;let r=[[`OD`,n.outer_diameter_m],[`WT`,n.wall_thickness_m]],i=e.map(e=>e.metadata?.bend_geometry).find(e=>e?.radius);i&&r.push([`R`,i.radius]);let a=r.filter(([,e])=>Number.isFinite(Number(e))).map(([e,n])=>`${e} ${ie(n,`m`,t)}`);return a.length>0?`${a.join(` · `)} ${j(`m`,t)}`:null}function Kr(e){let t=Lr(e);if(!t)return[];let n=[],r=t.element_families?.[0];r?n.push(`${r.element_count} ${r.family}`):Number.isFinite(t.element_count)&&n.push(`${t.element_count} elements`),Number.isFinite(t.node_count)&&n.push(`${t.node_count} nodes`);let i=(t.modelisations??[]).map(e=>e.modelisation).filter(Boolean);return i.length>0&&n.push(i.join(` + `)),n.length>0?[n.join(` · `)]:[]}function qr(e){let t=Rr(e);if(!t)return[];let n=t.data??{},r=[],i=n.section_profile;i&&r.push(`${i.sectors} sectors × ${i.layers} layers · NSEC ${i.nsec} · NCOU ${i.ncou}`);let a=Number(n.rendered_count),o=Number(n.total_count);return Number.isFinite(a)&&r.push(Number.isFinite(o)&&o>a?`${a} of ${o} points drawn`:`${a} points`),r}function Jr(e){let t=[],n=Yr(e);if(n){let r=N(n.value,`m`,O(e));t.push(`max |D| ${r}${n.nodeId?` at ${n.nodeId}`:``}`)}let r=Vt(e);return r>1&&t.push(`drawn at ×${oe(r)} (display only)`),t}function Yr(e){let t=(e.overlays??[]).find(t=>t.data?.result_type===`displacement`&&(!e.activeResultStateId||!t.data?.result_state_id||t.data.result_state_id===e.activeResultStateId))?.data?.values??{},n=null;for(let[e,r]of Object.entries(t)){let t=Array.isArray(r)?Math.hypot(...r.slice(0,3).map(Number)):Number(r);Number.isFinite(t)&&(!n||t>n.value)&&(n={nodeId:e,value:t})}return n}function Xr(e){let t=e.geometryStates??[],n=e=>{let t=e.data??{};return t.purpose===`visualization`||![`cold`,`design`].includes(String(t.state_type??``))},r=t.find(t=>(t.data?.id??t.id)===e.activeGeometryStateId);return r&&n(r)?r:t.find(n)??r??t[0]??null}function Zr(e){let t=Rr(e)?.data?.peak;if(!t)return null;let n=[];return t.element_id&&n.push(t.element_id),Number.isFinite(Number(t.angle_deg))&&n.push(`${oe(t.angle_deg)}°`),t.wall_position&&n.push(String(t.wall_position).replace(/_/g,` `)),{...t,location:n.join(` · `)}}function Qr(e){let t=Rr(e);if(!t)return[];let n=(e.geometryAssets??[]).find(e=>(e.object_ids??[]).some(e=>(t.object_ids??[]).includes(e)));if(!n)return[];let r={...(e.geometryPayloads??[]).find(e=>e.asset_id===n.id)?.generation_config??{},...n.generation_config??{}},i=r.sector_indices??[],a=r.layer_indices??[],o=r.values??[],s=[];for(let e=0;e<i.length;e+=1)!Number.isFinite(Number(i[e]))||!Number.isFinite(Number(a[e]))||s.push({sectorIndex:Number(i[e]),layerIndex:Number(a[e]),value:Number(o[e])});return s}function $r(e,t,n){return Math.min(Math.max(e,t),n)}function ei(e,t={}){let n=t.groupBy??`engineering`;if(n===`engineering`)return ti(e);let r=new Map;for(let t of e.objects){let i=bi(t,n,e),a=`${n}:${i}`;r.has(a)||r.set(a,{id:a,label:i,objectIds:[],children:[]}),r.get(a).objectIds.push(t.id)}return{id:`root`,label:`Scene`,objectIds:[],children:[...r.values()]}}function ti(e){let t=e.objects??[],n=t.filter(e=>!ri(e)),r=new Map;for(let e of n)!ni(e)||typeof e.entity_ref!=`string`||(!r.has(e.entity_ref)||[`pipe`,`beam`].includes(e.kind))&&r.set(e.entity_ref,e);let i=n.map(e=>({id:`engineering:${e.id}`,label:e.name||e.id,objectIds:[e.id],children:[]})),a=new Map(i.map(e=>[e.objectIds[0],e])),o={id:`engineering:analysis`,label:`Unmapped analysis`,objectIds:[],children:[]};for(let e of t.filter(ri)){let t=r.get(m(e))??r.get(e.metadata?.source_ref),n=a.get(t?.id)??o;n.objectIds.push(e.id),n.children.push({id:e.id,label:e.name||e.id,objectIds:[e.id],children:[]})}return o.objectIds.length&&i.push(o),{id:`root`,label:`Scene`,objectIds:[],children:i}}function ni(e){return[`pipe`,`beam`,`support`,`obstacle`,`equipment`,`rack_member`].includes(e.kind)}function ri(e){return/^(analysis_mesh|deformed_|solver_result|result_)/.test(e.kind??``)||[`geometry_state`,`displacement_vector`,`reaction_vector`,`reaction_moment_vector`,`tuyau_subpoint_field`].includes(e.kind)}var ii=Object.freeze([{key:`name`,read:e=>e.name},{key:`entity_ref`,read:e=>oi(e.entity_ref)},{key:`id`,read:e=>e.id},{key:`kind`,read:e=>e.kind},{key:`material`,read:e=>e.metadata?.material},{key:`route`,read:e=>e.metadata?.route??e.metadata?.attributes?.route},{key:`group`,read:e=>e.group_ids?.[0]??e.metadata?.groups?.[0]??e.metadata?.group},{key:`insulation`,read:e=>e.metadata?.insulation?.material??e.metadata?.insulation?.id},{key:`attribute`,read:e=>ai(e.metadata?.attributes)}]);function ai(e){return!e||typeof e!=`object`?``:Object.values(e).filter(e=>typeof e==`string`).join(` `)}function oi(e){return typeof e==`string`?e:e?.kind&&e?.id?`${e.kind}:${e.id}`:``}function si(e,t){let n=String(t??``).trim().toLowerCase();if(!n)return(e.objects??[]).map(e=>({object:e,field:null,start:-1,end:-1,rank:0}));let r=[];for(let t of e.objects??[])for(let e=0;e<ii.length;e+=1){let i=ii[e],a=i.read(t);if(typeof a!=`string`&&typeof a!=`number`)continue;let o=String(a).toLowerCase().indexOf(n);if(!(o<0)){r.push({object:t,field:i.key,start:o,end:o+n.length,rank:e});break}}return r.sort((e,t)=>e.rank-t.rank)}function ci(e,t={}){return(e.issues??[]).filter(n=>{if(t.type&&n.type!==t.type||t.status&&n.status!==t.status||t.severity&&n.severity!==t.severity)return!1;let r=Ci(e,n);return!(t.loadCase&&r.load_case!==t.loadCase||t.operatingOnly&&!wi(r))})}function li(e,t={}){let n=new Map;for(let r of ci(e,t)){let t=Ci(e,r),i=r.severity||`info`,a=t.load_case||`no_load_case`,o=e.issueReviewState?.[r.id]?.status||r.status||`open`,s=`${i}:${a}:${o}`;n.has(s)||n.set(s,{id:s,severity:i,loadCase:a,status:o,issues:[]}),n.get(s).issues.push(r)}return[...n.values()]}function ui(e,t){let n=Ci(e,t),r=n.clash??n,i=r?.penetration_m;if(Number.isFinite(i)&&i>0)return i;let a=r?.distance_m,o=r?.metadata?.operating_distance_m??r?.metadata?.cold_distance_m;return Number.isFinite(a)&&Number.isFinite(o)&&o>a?o-a:0}function di(e,t){let n=Ci(e,t);return n.object_pair??n.clash_review?.object_pair??t.entity_refs??[]}function fi(e,t={},{limit:n=25}={}){return li(e,t).map(t=>{let r=[...t.issues].sort((t,n)=>ui(e,n)-ui(e,t));return{...t,issues:r,total:r.length,shown:r.slice(0,n)}}).sort((t,n)=>{let r=Math.max(0,...t.issues.map(t=>ui(e,t)))-Math.max(0,...n.issues.map(t=>ui(e,t)));return Math.abs(r)>1e-9?-r:t.severity.localeCompare(n.severity)})}function pi(e,t){let n=(e.issues??[]).find(e=>e.id===t);if(!n)return e;let r=(e.views??[]).find(e=>e.id===n.view_id||e.issue_id===n.id),i=r?.selected_object_ids?.length?[...r.selected_object_ids]:xi(e,n),a=r?.active_overlay_ids?.length?[...r.active_overlay_ids]:Si(e,n.id).map(e=>e.id);return yi({...e,activeIssueId:n.id,activeOverlayIds:a,selectedObjectIds:i,camera:r?.camera??e.camera,sectionBox:r?.section_box??e.sectionBox})}function mi(e,t){let n=(e.issues??[]).find(e=>e.id===t);if(!n)return null;let r=xi(e,n).map(t=>e.objects.find(e=>e.id===t)).filter(Boolean).filter(e=>e.kind!==`clash_marker`);return{id:n.id,type:n.type,title:n.title,severity:n.severity,status:e.issueReviewState?.[n.id]?.status||n.status,comment:e.issueReviewState?.[n.id]?.comment||``,review:Ci(e,n),relatedObjects:r}}function hi(e,t){return yi({...e,sectionBox:t})}function gi(e){let t=Math.max(1,...e.map(e=>Math.abs(Number(e))))*1e-6,n=e.slice(0,3).map(Number),r=e.slice(3,6).map(Number);for(let e=0;e<3;e+=1)n[e]===r[e]&&(n[e]-=t,r[e]+=t);return{min:n,max:r}}function _i(e,t){return{id:`view:${Ti(t)}`,name:t,camera:e.camera,selectedObjectIds:[...e.selectedObjectIds??[]],hiddenObjectIds:[...e.hiddenObjectIds??[]],isolatedObjectIds:[...e.isolatedObjectIds??[]],sectionBox:e.sectionBox,visibleLayers:Object.fromEntries(Object.entries(e.layers).map(([e,t])=>[e,t.visible]))}}function vi(e,t){let n={...e.layers};for(let[e,r]of Object.entries(t.visibleLayers??{}))n[e]&&(n[e]={...n[e],visible:r});return yi({...e,camera:t.camera??e.camera,selectedObjectIds:[...t.selectedObjectIds??[]],hiddenObjectIds:[...t.hiddenObjectIds??[]],isolatedObjectIds:[...t.isolatedObjectIds??[]],sectionBox:t.sectionBox,layers:n})}function yi(e){return{...e,visibleObjectIds:Zn(e)}}function bi(e,t,n){if(t===`body`){for(let t of n?.objectLayerIds?.[e.id]??[]){let e=Or(t,n?.layers?.[t]?.category);if(e)return e}return`other`}return t===`kind`?e.kind||`object`:t===`material`?e.metadata?.material||`unassigned`:t===`route`?e.metadata?.route||e.metadata?.attributes?.route||`unassigned`:t===`group`?e.group_ids?.[0]||e.metadata?.groups?.[0]||e.metadata?.group||`unassigned`:t===`source`?e.source?.analysis_mesh?.id||e.source?.model?.id||e.metadata?.source||e.metadata?.source_ref||`model`:e[t]||e.metadata?.[t]||`unassigned`}function xi(e,t){let n=new Set;for(let e of t.object_ids??[])n.add(e);for(let r of t.entity_refs??[]){let t=e.objects.find(e=>e.entity_ref===r);t&&n.add(t.id)}for(let r of Si(e,t.id))for(let e of r.object_ids??[])n.add(e);return[...n]}function Si(e,t){return(e.overlays??[]).filter(e=>(e.data?.issue_ids??[]).includes(t))}function Ci(e,t){let n=(e.objects??[]).find(e=>e.kind===`clash_marker`&&(e.metadata?.issue_id===t.id||e.entity_ref===t.id||e.entity_ref===`issue:${t.id}`))?.metadata??{},r=n.review??{},i=n.clash??n.clash_metadata??{};return{...t.metadata??{},...i,...r,cold_distance_m:t.metadata?.cold_distance_m??n.cold_distance_m??i.cold_distance_m??r.cold_distance_m,operating_distance_m:t.metadata?.operating_distance_m??n.operating_distance_m??i.operating_distance_m??r.operating_distance_m,penetration_m:t.metadata?.penetration_m??n.penetration_m??i.penetration_m??r.penetration_m,envelope_type:t.metadata?.envelope_type??n.envelope_type??i.envelope_type??r.envelope_type,load_case:t.metadata?.load_case??n.load_case??i.load_case??r.load_case,introduced_by_deformation:!!(t.metadata?.introduced_by_deformation??n.introduced_by_deformation??i.introduced_by_deformation??r.introduced_by_deformation)}}function wi(e){return!!(e.introduced_by_deformation||e.operating_only||e.operating_distance_m!==void 0&&e.cold_distance_m!==void 0&&Number(e.operating_distance_m)<Number(e.cold_distance_m))}function Ti(e){return String(e).trim().toLowerCase().replace(/[^a-z0-9]+/g,`_`).replace(/^_+|_+$/g,``)}var Ei={LEFT:0,MIDDLE:1,RIGHT:2,ROTATE:0,DOLLY:1,PAN:2},Di={ROTATE:0,PAN:1,DOLLY_PAN:2,DOLLY_ROTATE:3},Oi=1e3,ki=1001,Ai=1002,ji=1003,Mi=1004,Ni=1005,Pi=1006,Fi=1007,Ii=1008,Li=1009,Ri=1010,zi=1011,Bi=1012,Vi=1013,Hi=1014,Ui=1015,Wi=1016,Gi=1017,Ki=1018,qi=1020,Ji=35902,Yi=35899,Xi=1021,Zi=1022,Qi=1023,$i=1026,ea=1027,ta=1028,na=1029,ra=1030,ia=1031,aa=1033,oa=33776,sa=33777,ca=33778,la=33779,ua=35840,da=35841,fa=35842,pa=35843,ma=36196,ha=37492,ga=37496,_a=37488,va=37489,ya=37490,ba=37491,xa=37808,Sa=37809,Ca=37810,wa=37811,Ta=37812,Ea=37813,Da=37814,Oa=37815,ka=37816,Aa=37817,ja=37818,Ma=37819,Na=37820,Pa=37821,Fa=36492,Ia=36494,La=36495,Ra=36283,za=36284,Ba=36285,Va=36286,Ha=2300,Ua=2301,Wa=2302,Ga=2303,Ka=2400,qa=2401,Ja=2402,Ya=3200,Xa=3201,Za=`srgb`,Qa=`srgb-linear`,$a=`linear`,eo=`srgb`,to=7680,no=35044,ro=2e3;function io(e){for(let t=e.length-1;t>=0;--t)if(e[t]>=65535)return!0;return!1}function ao(e){return ArrayBuffer.isView(e)&&!(e instanceof DataView)}function oo(e){return document.createElementNS(`http://www.w3.org/1999/xhtml`,e)}function so(){let e=oo(`canvas`);return e.style.display=`block`,e}var co={},lo=null;function uo(...e){let t=`THREE.`+e.shift();lo?lo(`log`,t,...e):console.log(t,...e)}function fo(e){let t=e[0];if(typeof t==`string`&&t.startsWith(`TSL:`)){let t=e[1];t&&t.isStackTrace?e[0]+=` `+t.getLocation():e[1]=`Stack trace not available. Enable "THREE.Node.captureStackTrace" to capture stack traces.`}return e}function R(...e){e=fo(e);let t=`THREE.`+e.shift();if(lo)lo(`warn`,t,...e);else{let n=e[0];n&&n.isStackTrace?console.warn(n.getError(t)):console.warn(t,...e)}}function z(...e){e=fo(e);let t=`THREE.`+e.shift();if(lo)lo(`error`,t,...e);else{let n=e[0];n&&n.isStackTrace?console.error(n.getError(t)):console.error(t,...e)}}function po(...e){let t=e.join(` `);t in co||(co[t]=!0,R(...e))}function mo(e,t,n){return new Promise(function(r,i){function a(){switch(e.clientWaitSync(t,e.SYNC_FLUSH_COMMANDS_BIT,0)){case e.WAIT_FAILED:i();break;case e.TIMEOUT_EXPIRED:setTimeout(a,n);break;default:r()}}setTimeout(a,n)})}var ho={0:1,2:6,4:7,3:5,1:0,6:2,7:4,5:3},go=class{addEventListener(e,t){this._listeners===void 0&&(this._listeners={});let n=this._listeners;n[e]===void 0&&(n[e]=[]),n[e].indexOf(t)===-1&&n[e].push(t)}hasEventListener(e,t){let n=this._listeners;return n===void 0?!1:n[e]!==void 0&&n[e].indexOf(t)!==-1}removeEventListener(e,t){let n=this._listeners;if(n===void 0)return;let r=n[e];if(r!==void 0){let e=r.indexOf(t);e!==-1&&r.splice(e,1)}}dispatchEvent(e){let t=this._listeners;if(t===void 0)return;let n=t[e.type];if(n!==void 0){e.target=this;let t=n.slice(0);for(let n=0,r=t.length;n<r;n++)t[n].call(this,e);e.target=null}}},_o=`00.01.02.03.04.05.06.07.08.09.0a.0b.0c.0d.0e.0f.10.11.12.13.14.15.16.17.18.19.1a.1b.1c.1d.1e.1f.20.21.22.23.24.25.26.27.28.29.2a.2b.2c.2d.2e.2f.30.31.32.33.34.35.36.37.38.39.3a.3b.3c.3d.3e.3f.40.41.42.43.44.45.46.47.48.49.4a.4b.4c.4d.4e.4f.50.51.52.53.54.55.56.57.58.59.5a.5b.5c.5d.5e.5f.60.61.62.63.64.65.66.67.68.69.6a.6b.6c.6d.6e.6f.70.71.72.73.74.75.76.77.78.79.7a.7b.7c.7d.7e.7f.80.81.82.83.84.85.86.87.88.89.8a.8b.8c.8d.8e.8f.90.91.92.93.94.95.96.97.98.99.9a.9b.9c.9d.9e.9f.a0.a1.a2.a3.a4.a5.a6.a7.a8.a9.aa.ab.ac.ad.ae.af.b0.b1.b2.b3.b4.b5.b6.b7.b8.b9.ba.bb.bc.bd.be.bf.c0.c1.c2.c3.c4.c5.c6.c7.c8.c9.ca.cb.cc.cd.ce.cf.d0.d1.d2.d3.d4.d5.d6.d7.d8.d9.da.db.dc.dd.de.df.e0.e1.e2.e3.e4.e5.e6.e7.e8.e9.ea.eb.ec.ed.ee.ef.f0.f1.f2.f3.f4.f5.f6.f7.f8.f9.fa.fb.fc.fd.fe.ff`.split(`.`),vo=1234567,yo=Math.PI/180,bo=180/Math.PI;function xo(){let e=Math.random()*4294967295|0,t=Math.random()*4294967295|0,n=Math.random()*4294967295|0,r=Math.random()*4294967295|0;return(_o[e&255]+_o[e>>8&255]+_o[e>>16&255]+_o[e>>24&255]+`-`+_o[t&255]+_o[t>>8&255]+`-`+_o[t>>16&15|64]+_o[t>>24&255]+`-`+_o[n&63|128]+_o[n>>8&255]+`-`+_o[n>>16&255]+_o[n>>24&255]+_o[r&255]+_o[r>>8&255]+_o[r>>16&255]+_o[r>>24&255]).toLowerCase()}function B(e,t,n){return Math.max(t,Math.min(n,e))}function So(e,t){return(e%t+t)%t}function Co(e,t,n,r,i){return r+(e-t)*(i-r)/(n-t)}function wo(e,t,n){return e===t?0:(n-e)/(t-e)}function To(e,t,n){return(1-n)*e+n*t}function Eo(e,t,n,r){return To(e,t,1-Math.exp(-n*r))}function Do(e,t=1){return t-Math.abs(So(e,t*2)-t)}function Oo(e,t,n){return e<=t?0:e>=n?1:(e=(e-t)/(n-t),e*e*(3-2*e))}function ko(e,t,n){return e<=t?0:e>=n?1:(e=(e-t)/(n-t),e*e*e*(e*(e*6-15)+10))}function Ao(e,t){return e+Math.floor(Math.random()*(t-e+1))}function jo(e,t){return e+Math.random()*(t-e)}function Mo(e){return e*(.5-Math.random())}function No(e){e!==void 0&&(vo=e);let t=vo+=1831565813;return t=Math.imul(t^t>>>15,t|1),t^=t+Math.imul(t^t>>>7,t|61),((t^t>>>14)>>>0)/4294967296}function Po(e){return e*yo}function Fo(e){return e*bo}function Io(e){return(e&e-1)==0&&e!==0}function Lo(e){return 2**Math.ceil(Math.log(e)/Math.LN2)}function Ro(e){return 2**Math.floor(Math.log(e)/Math.LN2)}function zo(e,t,n,r,i){let a=Math.cos,o=Math.sin,s=a(n/2),c=o(n/2),l=a((t+r)/2),u=o((t+r)/2),d=a((t-r)/2),f=o((t-r)/2),p=a((r-t)/2),m=o((r-t)/2);switch(i){case`XYX`:e.set(s*u,c*d,c*f,s*l);break;case`YZY`:e.set(c*f,s*u,c*d,s*l);break;case`ZXZ`:e.set(c*d,c*f,s*u,s*l);break;case`XZX`:e.set(s*u,c*m,c*p,s*l);break;case`YXY`:e.set(c*p,s*u,c*m,s*l);break;case`ZYZ`:e.set(c*m,c*p,s*u,s*l);break;default:R(`MathUtils: .setQuaternionFromProperEuler() encountered an unknown order: `+i)}}function Bo(e,t){switch(t.constructor){case Float32Array:return e;case Uint32Array:return e/4294967295;case Uint16Array:return e/65535;case Uint8Array:return e/255;case Int32Array:return Math.max(e/2147483647,-1);case Int16Array:return Math.max(e/32767,-1);case Int8Array:return Math.max(e/127,-1);default:throw Error(`Invalid component type.`)}}function Vo(e,t){switch(t.constructor){case Float32Array:return e;case Uint32Array:return Math.round(e*4294967295);case Uint16Array:return Math.round(e*65535);case Uint8Array:return Math.round(e*255);case Int32Array:return Math.round(e*2147483647);case Int16Array:return Math.round(e*32767);case Int8Array:return Math.round(e*127);default:throw Error(`Invalid component type.`)}}var Ho={DEG2RAD:yo,RAD2DEG:bo,generateUUID:xo,clamp:B,euclideanModulo:So,mapLinear:Co,inverseLerp:wo,lerp:To,damp:Eo,pingpong:Do,smoothstep:Oo,smootherstep:ko,randInt:Ao,randFloat:jo,randFloatSpread:Mo,seededRandom:No,degToRad:Po,radToDeg:Fo,isPowerOfTwo:Io,ceilPowerOfTwo:Lo,floorPowerOfTwo:Ro,setQuaternionFromProperEuler:zo,normalize:Vo,denormalize:Bo},V=class e{static{e.prototype.isVector2=!0}constructor(e=0,t=0){this.x=e,this.y=t}get width(){return this.x}set width(e){this.x=e}get height(){return this.y}set height(e){this.y=e}set(e,t){return this.x=e,this.y=t,this}setScalar(e){return this.x=e,this.y=e,this}setX(e){return this.x=e,this}setY(e){return this.y=e,this}setComponent(e,t){switch(e){case 0:this.x=t;break;case 1:this.y=t;break;default:throw Error(`index is out of range: `+e)}return this}getComponent(e){switch(e){case 0:return this.x;case 1:return this.y;default:throw Error(`index is out of range: `+e)}}clone(){return new this.constructor(this.x,this.y)}copy(e){return this.x=e.x,this.y=e.y,this}add(e){return this.x+=e.x,this.y+=e.y,this}addScalar(e){return this.x+=e,this.y+=e,this}addVectors(e,t){return this.x=e.x+t.x,this.y=e.y+t.y,this}addScaledVector(e,t){return this.x+=e.x*t,this.y+=e.y*t,this}sub(e){return this.x-=e.x,this.y-=e.y,this}subScalar(e){return this.x-=e,this.y-=e,this}subVectors(e,t){return this.x=e.x-t.x,this.y=e.y-t.y,this}multiply(e){return this.x*=e.x,this.y*=e.y,this}multiplyScalar(e){return this.x*=e,this.y*=e,this}divide(e){return this.x/=e.x,this.y/=e.y,this}divideScalar(e){return this.multiplyScalar(1/e)}applyMatrix3(e){let t=this.x,n=this.y,r=e.elements;return this.x=r[0]*t+r[3]*n+r[6],this.y=r[1]*t+r[4]*n+r[7],this}min(e){return this.x=Math.min(this.x,e.x),this.y=Math.min(this.y,e.y),this}max(e){return this.x=Math.max(this.x,e.x),this.y=Math.max(this.y,e.y),this}clamp(e,t){return this.x=B(this.x,e.x,t.x),this.y=B(this.y,e.y,t.y),this}clampScalar(e,t){return this.x=B(this.x,e,t),this.y=B(this.y,e,t),this}clampLength(e,t){let n=this.length();return this.divideScalar(n||1).multiplyScalar(B(n,e,t))}floor(){return this.x=Math.floor(this.x),this.y=Math.floor(this.y),this}ceil(){return this.x=Math.ceil(this.x),this.y=Math.ceil(this.y),this}round(){return this.x=Math.round(this.x),this.y=Math.round(this.y),this}roundToZero(){return this.x=Math.trunc(this.x),this.y=Math.trunc(this.y),this}negate(){return this.x=-this.x,this.y=-this.y,this}dot(e){return this.x*e.x+this.y*e.y}cross(e){return this.x*e.y-this.y*e.x}lengthSq(){return this.x*this.x+this.y*this.y}length(){return Math.sqrt(this.x*this.x+this.y*this.y)}manhattanLength(){return Math.abs(this.x)+Math.abs(this.y)}normalize(){return this.divideScalar(this.length()||1)}angle(){return Math.atan2(-this.y,-this.x)+Math.PI}angleTo(e){let t=Math.sqrt(this.lengthSq()*e.lengthSq());if(t===0)return Math.PI/2;let n=this.dot(e)/t;return Math.acos(B(n,-1,1))}distanceTo(e){return Math.sqrt(this.distanceToSquared(e))}distanceToSquared(e){let t=this.x-e.x,n=this.y-e.y;return t*t+n*n}manhattanDistanceTo(e){return Math.abs(this.x-e.x)+Math.abs(this.y-e.y)}setLength(e){return this.normalize().multiplyScalar(e)}lerp(e,t){return this.x+=(e.x-this.x)*t,this.y+=(e.y-this.y)*t,this}lerpVectors(e,t,n){return this.x=e.x+(t.x-e.x)*n,this.y=e.y+(t.y-e.y)*n,this}equals(e){return e.x===this.x&&e.y===this.y}fromArray(e,t=0){return this.x=e[t],this.y=e[t+1],this}toArray(e=[],t=0){return e[t]=this.x,e[t+1]=this.y,e}fromBufferAttribute(e,t){return this.x=e.getX(t),this.y=e.getY(t),this}rotateAround(e,t){let n=Math.cos(t),r=Math.sin(t),i=this.x-e.x,a=this.y-e.y;return this.x=i*n-a*r+e.x,this.y=i*r+a*n+e.y,this}random(){return this.x=Math.random(),this.y=Math.random(),this}*[Symbol.iterator](){yield this.x,yield this.y}},Uo=class{constructor(e=0,t=0,n=0,r=1){this.isQuaternion=!0,this._x=e,this._y=t,this._z=n,this._w=r}static slerpFlat(e,t,n,r,i,a,o){let s=n[r+0],c=n[r+1],l=n[r+2],u=n[r+3],d=i[a+0],f=i[a+1],p=i[a+2],m=i[a+3];if(u!==m||s!==d||c!==f||l!==p){let e=s*d+c*f+l*p+u*m;e<0&&(d=-d,f=-f,p=-p,m=-m,e=-e);let t=1-o;if(e<.9995){let n=Math.acos(e),r=Math.sin(n);t=Math.sin(t*n)/r,o=Math.sin(o*n)/r,s=s*t+d*o,c=c*t+f*o,l=l*t+p*o,u=u*t+m*o}else{s=s*t+d*o,c=c*t+f*o,l=l*t+p*o,u=u*t+m*o;let e=1/Math.sqrt(s*s+c*c+l*l+u*u);s*=e,c*=e,l*=e,u*=e}}e[t]=s,e[t+1]=c,e[t+2]=l,e[t+3]=u}static multiplyQuaternionsFlat(e,t,n,r,i,a){let o=n[r],s=n[r+1],c=n[r+2],l=n[r+3],u=i[a],d=i[a+1],f=i[a+2],p=i[a+3];return e[t]=o*p+l*u+s*f-c*d,e[t+1]=s*p+l*d+c*u-o*f,e[t+2]=c*p+l*f+o*d-s*u,e[t+3]=l*p-o*u-s*d-c*f,e}get x(){return this._x}set x(e){this._x=e,this._onChangeCallback()}get y(){return this._y}set y(e){this._y=e,this._onChangeCallback()}get z(){return this._z}set z(e){this._z=e,this._onChangeCallback()}get w(){return this._w}set w(e){this._w=e,this._onChangeCallback()}set(e,t,n,r){return this._x=e,this._y=t,this._z=n,this._w=r,this._onChangeCallback(),this}clone(){return new this.constructor(this._x,this._y,this._z,this._w)}copy(e){return this._x=e.x,this._y=e.y,this._z=e.z,this._w=e.w,this._onChangeCallback(),this}setFromEuler(e,t=!0){let n=e._x,r=e._y,i=e._z,a=e._order,o=Math.cos,s=Math.sin,c=o(n/2),l=o(r/2),u=o(i/2),d=s(n/2),f=s(r/2),p=s(i/2);switch(a){case`XYZ`:this._x=d*l*u+c*f*p,this._y=c*f*u-d*l*p,this._z=c*l*p+d*f*u,this._w=c*l*u-d*f*p;break;case`YXZ`:this._x=d*l*u+c*f*p,this._y=c*f*u-d*l*p,this._z=c*l*p-d*f*u,this._w=c*l*u+d*f*p;break;case`ZXY`:this._x=d*l*u-c*f*p,this._y=c*f*u+d*l*p,this._z=c*l*p+d*f*u,this._w=c*l*u-d*f*p;break;case`ZYX`:this._x=d*l*u-c*f*p,this._y=c*f*u+d*l*p,this._z=c*l*p-d*f*u,this._w=c*l*u+d*f*p;break;case`YZX`:this._x=d*l*u+c*f*p,this._y=c*f*u+d*l*p,this._z=c*l*p-d*f*u,this._w=c*l*u-d*f*p;break;case`XZY`:this._x=d*l*u-c*f*p,this._y=c*f*u-d*l*p,this._z=c*l*p+d*f*u,this._w=c*l*u+d*f*p;break;default:R(`Quaternion: .setFromEuler() encountered an unknown order: `+a)}return t===!0&&this._onChangeCallback(),this}setFromAxisAngle(e,t){let n=t/2,r=Math.sin(n);return this._x=e.x*r,this._y=e.y*r,this._z=e.z*r,this._w=Math.cos(n),this._onChangeCallback(),this}setFromRotationMatrix(e){let t=e.elements,n=t[0],r=t[4],i=t[8],a=t[1],o=t[5],s=t[9],c=t[2],l=t[6],u=t[10],d=n+o+u;if(d>0){let e=.5/Math.sqrt(d+1);this._w=.25/e,this._x=(l-s)*e,this._y=(i-c)*e,this._z=(a-r)*e}else if(n>o&&n>u){let e=2*Math.sqrt(1+n-o-u);this._w=(l-s)/e,this._x=.25*e,this._y=(r+a)/e,this._z=(i+c)/e}else if(o>u){let e=2*Math.sqrt(1+o-n-u);this._w=(i-c)/e,this._x=(r+a)/e,this._y=.25*e,this._z=(s+l)/e}else{let e=2*Math.sqrt(1+u-n-o);this._w=(a-r)/e,this._x=(i+c)/e,this._y=(s+l)/e,this._z=.25*e}return this._onChangeCallback(),this}setFromUnitVectors(e,t){let n=e.dot(t)+1;return n<1e-8?(n=0,Math.abs(e.x)>Math.abs(e.z)?(this._x=-e.y,this._y=e.x,this._z=0,this._w=n):(this._x=0,this._y=-e.z,this._z=e.y,this._w=n)):(this._x=e.y*t.z-e.z*t.y,this._y=e.z*t.x-e.x*t.z,this._z=e.x*t.y-e.y*t.x,this._w=n),this.normalize()}angleTo(e){return 2*Math.acos(Math.abs(B(this.dot(e),-1,1)))}rotateTowards(e,t){let n=this.angleTo(e);if(n===0)return this;let r=Math.min(1,t/n);return this.slerp(e,r),this}identity(){return this.set(0,0,0,1)}invert(){return this.conjugate()}conjugate(){return this._x*=-1,this._y*=-1,this._z*=-1,this._onChangeCallback(),this}dot(e){return this._x*e._x+this._y*e._y+this._z*e._z+this._w*e._w}lengthSq(){return this._x*this._x+this._y*this._y+this._z*this._z+this._w*this._w}length(){return Math.sqrt(this._x*this._x+this._y*this._y+this._z*this._z+this._w*this._w)}normalize(){let e=this.length();return e===0?(this._x=0,this._y=0,this._z=0,this._w=1):(e=1/e,this._x*=e,this._y*=e,this._z*=e,this._w*=e),this._onChangeCallback(),this}multiply(e){return this.multiplyQuaternions(this,e)}premultiply(e){return this.multiplyQuaternions(e,this)}multiplyQuaternions(e,t){let n=e._x,r=e._y,i=e._z,a=e._w,o=t._x,s=t._y,c=t._z,l=t._w;return this._x=n*l+a*o+r*c-i*s,this._y=r*l+a*s+i*o-n*c,this._z=i*l+a*c+n*s-r*o,this._w=a*l-n*o-r*s-i*c,this._onChangeCallback(),this}slerp(e,t){let n=e._x,r=e._y,i=e._z,a=e._w,o=this.dot(e);o<0&&(n=-n,r=-r,i=-i,a=-a,o=-o);let s=1-t;if(o<.9995){let e=Math.acos(o),c=Math.sin(e);s=Math.sin(s*e)/c,t=Math.sin(t*e)/c,this._x=this._x*s+n*t,this._y=this._y*s+r*t,this._z=this._z*s+i*t,this._w=this._w*s+a*t,this._onChangeCallback()}else this._x=this._x*s+n*t,this._y=this._y*s+r*t,this._z=this._z*s+i*t,this._w=this._w*s+a*t,this.normalize();return this}slerpQuaternions(e,t,n){return this.copy(e).slerp(t,n)}random(){let e=2*Math.PI*Math.random(),t=2*Math.PI*Math.random(),n=Math.random(),r=Math.sqrt(1-n),i=Math.sqrt(n);return this.set(r*Math.sin(e),r*Math.cos(e),i*Math.sin(t),i*Math.cos(t))}equals(e){return e._x===this._x&&e._y===this._y&&e._z===this._z&&e._w===this._w}fromArray(e,t=0){return this._x=e[t],this._y=e[t+1],this._z=e[t+2],this._w=e[t+3],this._onChangeCallback(),this}toArray(e=[],t=0){return e[t]=this._x,e[t+1]=this._y,e[t+2]=this._z,e[t+3]=this._w,e}fromBufferAttribute(e,t){return this._x=e.getX(t),this._y=e.getY(t),this._z=e.getZ(t),this._w=e.getW(t),this._onChangeCallback(),this}toJSON(){return this.toArray()}_onChange(e){return this._onChangeCallback=e,this}_onChangeCallback(){}*[Symbol.iterator](){yield this._x,yield this._y,yield this._z,yield this._w}},H=class e{static{e.prototype.isVector3=!0}constructor(e=0,t=0,n=0){this.x=e,this.y=t,this.z=n}set(e,t,n){return n===void 0&&(n=this.z),this.x=e,this.y=t,this.z=n,this}setScalar(e){return this.x=e,this.y=e,this.z=e,this}setX(e){return this.x=e,this}setY(e){return this.y=e,this}setZ(e){return this.z=e,this}setComponent(e,t){switch(e){case 0:this.x=t;break;case 1:this.y=t;break;case 2:this.z=t;break;default:throw Error(`index is out of range: `+e)}return this}getComponent(e){switch(e){case 0:return this.x;case 1:return this.y;case 2:return this.z;default:throw Error(`index is out of range: `+e)}}clone(){return new this.constructor(this.x,this.y,this.z)}copy(e){return this.x=e.x,this.y=e.y,this.z=e.z,this}add(e){return this.x+=e.x,this.y+=e.y,this.z+=e.z,this}addScalar(e){return this.x+=e,this.y+=e,this.z+=e,this}addVectors(e,t){return this.x=e.x+t.x,this.y=e.y+t.y,this.z=e.z+t.z,this}addScaledVector(e,t){return this.x+=e.x*t,this.y+=e.y*t,this.z+=e.z*t,this}sub(e){return this.x-=e.x,this.y-=e.y,this.z-=e.z,this}subScalar(e){return this.x-=e,this.y-=e,this.z-=e,this}subVectors(e,t){return this.x=e.x-t.x,this.y=e.y-t.y,this.z=e.z-t.z,this}multiply(e){return this.x*=e.x,this.y*=e.y,this.z*=e.z,this}multiplyScalar(e){return this.x*=e,this.y*=e,this.z*=e,this}multiplyVectors(e,t){return this.x=e.x*t.x,this.y=e.y*t.y,this.z=e.z*t.z,this}applyEuler(e){return this.applyQuaternion(Go.setFromEuler(e))}applyAxisAngle(e,t){return this.applyQuaternion(Go.setFromAxisAngle(e,t))}applyMatrix3(e){let t=this.x,n=this.y,r=this.z,i=e.elements;return this.x=i[0]*t+i[3]*n+i[6]*r,this.y=i[1]*t+i[4]*n+i[7]*r,this.z=i[2]*t+i[5]*n+i[8]*r,this}applyNormalMatrix(e){return this.applyMatrix3(e).normalize()}applyMatrix4(e){let t=this.x,n=this.y,r=this.z,i=e.elements,a=1/(i[3]*t+i[7]*n+i[11]*r+i[15]);return this.x=(i[0]*t+i[4]*n+i[8]*r+i[12])*a,this.y=(i[1]*t+i[5]*n+i[9]*r+i[13])*a,this.z=(i[2]*t+i[6]*n+i[10]*r+i[14])*a,this}applyQuaternion(e){let t=this.x,n=this.y,r=this.z,i=e.x,a=e.y,o=e.z,s=e.w,c=2*(a*r-o*n),l=2*(o*t-i*r),u=2*(i*n-a*t);return this.x=t+s*c+a*u-o*l,this.y=n+s*l+o*c-i*u,this.z=r+s*u+i*l-a*c,this}project(e){return this.applyMatrix4(e.matrixWorldInverse).applyMatrix4(e.projectionMatrix)}unproject(e){return this.applyMatrix4(e.projectionMatrixInverse).applyMatrix4(e.matrixWorld)}transformDirection(e){let t=this.x,n=this.y,r=this.z,i=e.elements;return this.x=i[0]*t+i[4]*n+i[8]*r,this.y=i[1]*t+i[5]*n+i[9]*r,this.z=i[2]*t+i[6]*n+i[10]*r,this.normalize()}divide(e){return this.x/=e.x,this.y/=e.y,this.z/=e.z,this}divideScalar(e){return this.multiplyScalar(1/e)}min(e){return this.x=Math.min(this.x,e.x),this.y=Math.min(this.y,e.y),this.z=Math.min(this.z,e.z),this}max(e){return this.x=Math.max(this.x,e.x),this.y=Math.max(this.y,e.y),this.z=Math.max(this.z,e.z),this}clamp(e,t){return this.x=B(this.x,e.x,t.x),this.y=B(this.y,e.y,t.y),this.z=B(this.z,e.z,t.z),this}clampScalar(e,t){return this.x=B(this.x,e,t),this.y=B(this.y,e,t),this.z=B(this.z,e,t),this}clampLength(e,t){let n=this.length();return this.divideScalar(n||1).multiplyScalar(B(n,e,t))}floor(){return this.x=Math.floor(this.x),this.y=Math.floor(this.y),this.z=Math.floor(this.z),this}ceil(){return this.x=Math.ceil(this.x),this.y=Math.ceil(this.y),this.z=Math.ceil(this.z),this}round(){return this.x=Math.round(this.x),this.y=Math.round(this.y),this.z=Math.round(this.z),this}roundToZero(){return this.x=Math.trunc(this.x),this.y=Math.trunc(this.y),this.z=Math.trunc(this.z),this}negate(){return this.x=-this.x,this.y=-this.y,this.z=-this.z,this}dot(e){return this.x*e.x+this.y*e.y+this.z*e.z}lengthSq(){return this.x*this.x+this.y*this.y+this.z*this.z}length(){return Math.sqrt(this.x*this.x+this.y*this.y+this.z*this.z)}manhattanLength(){return Math.abs(this.x)+Math.abs(this.y)+Math.abs(this.z)}normalize(){return this.divideScalar(this.length()||1)}setLength(e){return this.normalize().multiplyScalar(e)}lerp(e,t){return this.x+=(e.x-this.x)*t,this.y+=(e.y-this.y)*t,this.z+=(e.z-this.z)*t,this}lerpVectors(e,t,n){return this.x=e.x+(t.x-e.x)*n,this.y=e.y+(t.y-e.y)*n,this.z=e.z+(t.z-e.z)*n,this}cross(e){return this.crossVectors(this,e)}crossVectors(e,t){let n=e.x,r=e.y,i=e.z,a=t.x,o=t.y,s=t.z;return this.x=r*s-i*o,this.y=i*a-n*s,this.z=n*o-r*a,this}projectOnVector(e){let t=e.lengthSq();if(t===0)return this.set(0,0,0);let n=e.dot(this)/t;return this.copy(e).multiplyScalar(n)}projectOnPlane(e){return Wo.copy(this).projectOnVector(e),this.sub(Wo)}reflect(e){return this.sub(Wo.copy(e).multiplyScalar(2*this.dot(e)))}angleTo(e){let t=Math.sqrt(this.lengthSq()*e.lengthSq());if(t===0)return Math.PI/2;let n=this.dot(e)/t;return Math.acos(B(n,-1,1))}distanceTo(e){return Math.sqrt(this.distanceToSquared(e))}distanceToSquared(e){let t=this.x-e.x,n=this.y-e.y,r=this.z-e.z;return t*t+n*n+r*r}manhattanDistanceTo(e){return Math.abs(this.x-e.x)+Math.abs(this.y-e.y)+Math.abs(this.z-e.z)}setFromSpherical(e){return this.setFromSphericalCoords(e.radius,e.phi,e.theta)}setFromSphericalCoords(e,t,n){let r=Math.sin(t)*e;return this.x=r*Math.sin(n),this.y=Math.cos(t)*e,this.z=r*Math.cos(n),this}setFromCylindrical(e){return this.setFromCylindricalCoords(e.radius,e.theta,e.y)}setFromCylindricalCoords(e,t,n){return this.x=e*Math.sin(t),this.y=n,this.z=e*Math.cos(t),this}setFromMatrixPosition(e){let t=e.elements;return this.x=t[12],this.y=t[13],this.z=t[14],this}setFromMatrixScale(e){let t=this.setFromMatrixColumn(e,0).length(),n=this.setFromMatrixColumn(e,1).length(),r=this.setFromMatrixColumn(e,2).length();return this.x=t,this.y=n,this.z=r,this}setFromMatrixColumn(e,t){return this.fromArray(e.elements,t*4)}setFromMatrix3Column(e,t){return this.fromArray(e.elements,t*3)}setFromEuler(e){return this.x=e._x,this.y=e._y,this.z=e._z,this}setFromColor(e){return this.x=e.r,this.y=e.g,this.z=e.b,this}equals(e){return e.x===this.x&&e.y===this.y&&e.z===this.z}fromArray(e,t=0){return this.x=e[t],this.y=e[t+1],this.z=e[t+2],this}toArray(e=[],t=0){return e[t]=this.x,e[t+1]=this.y,e[t+2]=this.z,e}fromBufferAttribute(e,t){return this.x=e.getX(t),this.y=e.getY(t),this.z=e.getZ(t),this}random(){return this.x=Math.random(),this.y=Math.random(),this.z=Math.random(),this}randomDirection(){let e=Math.random()*Math.PI*2,t=Math.random()*2-1,n=Math.sqrt(1-t*t);return this.x=n*Math.cos(e),this.y=t,this.z=n*Math.sin(e),this}*[Symbol.iterator](){yield this.x,yield this.y,yield this.z}},Wo=new H,Go=new Uo,U=class e{static{e.prototype.isMatrix3=!0}constructor(e,t,n,r,i,a,o,s,c){this.elements=[1,0,0,0,1,0,0,0,1],e!==void 0&&this.set(e,t,n,r,i,a,o,s,c)}set(e,t,n,r,i,a,o,s,c){let l=this.elements;return l[0]=e,l[1]=r,l[2]=o,l[3]=t,l[4]=i,l[5]=s,l[6]=n,l[7]=a,l[8]=c,this}identity(){return this.set(1,0,0,0,1,0,0,0,1),this}copy(e){let t=this.elements,n=e.elements;return t[0]=n[0],t[1]=n[1],t[2]=n[2],t[3]=n[3],t[4]=n[4],t[5]=n[5],t[6]=n[6],t[7]=n[7],t[8]=n[8],this}extractBasis(e,t,n){return e.setFromMatrix3Column(this,0),t.setFromMatrix3Column(this,1),n.setFromMatrix3Column(this,2),this}setFromMatrix4(e){let t=e.elements;return this.set(t[0],t[4],t[8],t[1],t[5],t[9],t[2],t[6],t[10]),this}multiply(e){return this.multiplyMatrices(this,e)}premultiply(e){return this.multiplyMatrices(e,this)}multiplyMatrices(e,t){let n=e.elements,r=t.elements,i=this.elements,a=n[0],o=n[3],s=n[6],c=n[1],l=n[4],u=n[7],d=n[2],f=n[5],p=n[8],m=r[0],h=r[3],g=r[6],_=r[1],v=r[4],y=r[7],b=r[2],x=r[5],S=r[8];return i[0]=a*m+o*_+s*b,i[3]=a*h+o*v+s*x,i[6]=a*g+o*y+s*S,i[1]=c*m+l*_+u*b,i[4]=c*h+l*v+u*x,i[7]=c*g+l*y+u*S,i[2]=d*m+f*_+p*b,i[5]=d*h+f*v+p*x,i[8]=d*g+f*y+p*S,this}multiplyScalar(e){let t=this.elements;return t[0]*=e,t[3]*=e,t[6]*=e,t[1]*=e,t[4]*=e,t[7]*=e,t[2]*=e,t[5]*=e,t[8]*=e,this}determinant(){let e=this.elements,t=e[0],n=e[1],r=e[2],i=e[3],a=e[4],o=e[5],s=e[6],c=e[7],l=e[8];return t*a*l-t*o*c-n*i*l+n*o*s+r*i*c-r*a*s}invert(){let e=this.elements,t=e[0],n=e[1],r=e[2],i=e[3],a=e[4],o=e[5],s=e[6],c=e[7],l=e[8],u=l*a-o*c,d=o*s-l*i,f=c*i-a*s,p=t*u+n*d+r*f;if(p===0)return this.set(0,0,0,0,0,0,0,0,0);let m=1/p;return e[0]=u*m,e[1]=(r*c-l*n)*m,e[2]=(o*n-r*a)*m,e[3]=d*m,e[4]=(l*t-r*s)*m,e[5]=(r*i-o*t)*m,e[6]=f*m,e[7]=(n*s-c*t)*m,e[8]=(a*t-n*i)*m,this}transpose(){let e,t=this.elements;return e=t[1],t[1]=t[3],t[3]=e,e=t[2],t[2]=t[6],t[6]=e,e=t[5],t[5]=t[7],t[7]=e,this}getNormalMatrix(e){return this.setFromMatrix4(e).invert().transpose()}transposeIntoArray(e){let t=this.elements;return e[0]=t[0],e[1]=t[3],e[2]=t[6],e[3]=t[1],e[4]=t[4],e[5]=t[7],e[6]=t[2],e[7]=t[5],e[8]=t[8],this}setUvTransform(e,t,n,r,i,a,o){let s=Math.cos(i),c=Math.sin(i);return this.set(n*s,n*c,-n*(s*a+c*o)+a+e,-r*c,r*s,-r*(-c*a+s*o)+o+t,0,0,1),this}scale(e,t){return this.premultiply(Ko.makeScale(e,t)),this}rotate(e){return this.premultiply(Ko.makeRotation(-e)),this}translate(e,t){return this.premultiply(Ko.makeTranslation(e,t)),this}makeTranslation(e,t){return e.isVector2?this.set(1,0,e.x,0,1,e.y,0,0,1):this.set(1,0,e,0,1,t,0,0,1),this}makeRotation(e){let t=Math.cos(e),n=Math.sin(e);return this.set(t,-n,0,n,t,0,0,0,1),this}makeScale(e,t){return this.set(e,0,0,0,t,0,0,0,1),this}equals(e){let t=this.elements,n=e.elements;for(let e=0;e<9;e++)if(t[e]!==n[e])return!1;return!0}fromArray(e,t=0){for(let n=0;n<9;n++)this.elements[n]=e[n+t];return this}toArray(e=[],t=0){let n=this.elements;return e[t]=n[0],e[t+1]=n[1],e[t+2]=n[2],e[t+3]=n[3],e[t+4]=n[4],e[t+5]=n[5],e[t+6]=n[6],e[t+7]=n[7],e[t+8]=n[8],e}clone(){return new this.constructor().fromArray(this.elements)}},Ko=new U,qo=new U().set(.4123908,.3575843,.1804808,.212639,.7151687,.0721923,.0193308,.1191948,.9505322),Jo=new U().set(3.2409699,-1.5373832,-.4986108,-.9692436,1.8759675,.0415551,.0556301,-.203977,1.0569715);function Yo(){let e={enabled:!0,workingColorSpace:Qa,spaces:{},convert:function(e,t,n){return this.enabled===!1||t===n||!t||!n?e:(this.spaces[t].transfer===`srgb`&&(e.r=Zo(e.r),e.g=Zo(e.g),e.b=Zo(e.b)),this.spaces[t].primaries!==this.spaces[n].primaries&&(e.applyMatrix3(this.spaces[t].toXYZ),e.applyMatrix3(this.spaces[n].fromXYZ)),this.spaces[n].transfer===`srgb`&&(e.r=Qo(e.r),e.g=Qo(e.g),e.b=Qo(e.b)),e)},workingToColorSpace:function(e,t){return this.convert(e,this.workingColorSpace,t)},colorSpaceToWorking:function(e,t){return this.convert(e,t,this.workingColorSpace)},getPrimaries:function(e){return this.spaces[e].primaries},getTransfer:function(e){return e===``?$a:this.spaces[e].transfer},getToneMappingMode:function(e){return this.spaces[e].outputColorSpaceConfig.toneMappingMode||`standard`},getLuminanceCoefficients:function(e,t=this.workingColorSpace){return e.fromArray(this.spaces[t].luminanceCoefficients)},define:function(e){Object.assign(this.spaces,e)},_getMatrix:function(e,t,n){return e.copy(this.spaces[t].toXYZ).multiply(this.spaces[n].fromXYZ)},_getDrawingBufferColorSpace:function(e){return this.spaces[e].outputColorSpaceConfig.drawingBufferColorSpace},_getUnpackColorSpace:function(e=this.workingColorSpace){return this.spaces[e].workingColorSpaceConfig.unpackColorSpace},fromWorkingColorSpace:function(t,n){return po(`ColorManagement: .fromWorkingColorSpace() has been renamed to .workingToColorSpace().`),e.workingToColorSpace(t,n)},toWorkingColorSpace:function(t,n){return po(`ColorManagement: .toWorkingColorSpace() has been renamed to .colorSpaceToWorking().`),e.colorSpaceToWorking(t,n)}},t=[.64,.33,.3,.6,.15,.06],n=[.2126,.7152,.0722],r=[.3127,.329];return e.define({[Qa]:{primaries:t,whitePoint:r,transfer:$a,toXYZ:qo,fromXYZ:Jo,luminanceCoefficients:n,workingColorSpaceConfig:{unpackColorSpace:Za},outputColorSpaceConfig:{drawingBufferColorSpace:Za}},[Za]:{primaries:t,whitePoint:r,transfer:eo,toXYZ:qo,fromXYZ:Jo,luminanceCoefficients:n,outputColorSpaceConfig:{drawingBufferColorSpace:Za}}}),e}var Xo=Yo();function Zo(e){return e<.04045?e*.0773993808:(e*.9478672986+.0521327014)**2.4}function Qo(e){return e<.0031308?e*12.92:1.055*e**.41666-.055}var $o,es=class{static getDataURL(e,t=`image/png`){if(/^data:/i.test(e.src)||typeof HTMLCanvasElement>`u`)return e.src;let n;if(e instanceof HTMLCanvasElement)n=e;else{$o===void 0&&($o=oo(`canvas`)),$o.width=e.width,$o.height=e.height;let t=$o.getContext(`2d`);e instanceof ImageData?t.putImageData(e,0,0):t.drawImage(e,0,0,e.width,e.height),n=$o}return n.toDataURL(t)}static sRGBToLinear(e){if(typeof HTMLImageElement<`u`&&e instanceof HTMLImageElement||typeof HTMLCanvasElement<`u`&&e instanceof HTMLCanvasElement||typeof ImageBitmap<`u`&&e instanceof ImageBitmap){let t=oo(`canvas`);t.width=e.width,t.height=e.height;let n=t.getContext(`2d`);n.drawImage(e,0,0,e.width,e.height);let r=n.getImageData(0,0,e.width,e.height),i=r.data;for(let e=0;e<i.length;e++)i[e]=Zo(i[e]/255)*255;return n.putImageData(r,0,0),t}else if(e.data){let t=e.data.slice(0);for(let e=0;e<t.length;e++)t instanceof Uint8Array||t instanceof Uint8ClampedArray?t[e]=Math.floor(Zo(t[e]/255)*255):t[e]=Zo(t[e]);return{data:t,width:e.width,height:e.height}}else return R(`ImageUtils.sRGBToLinear(): Unsupported image type. No color space conversion applied.`),e}},ts=0,ns=class{constructor(e=null){this.isSource=!0,Object.defineProperty(this,"id",{value:ts++}),this.uuid=xo(),this.data=e,this.dataReady=!0,this.version=0}getSize(e){let t=this.data;return typeof HTMLVideoElement<`u`&&t instanceof HTMLVideoElement?e.set(t.videoWidth,t.videoHeight,0):typeof VideoFrame<`u`&&t instanceof VideoFrame?e.set(t.displayWidth,t.displayHeight,0):t===null?e.set(0,0,0):e.set(t.width,t.height,t.depth||0),e}set needsUpdate(e){e===!0&&this.version++}toJSON(e){let t=e===void 0||typeof e==`string`;if(!t&&e.images[this.uuid]!==void 0)return e.images[this.uuid];let n={uuid:this.uuid,url:``},r=this.data;if(r!==null){let e;if(Array.isArray(r)){e=[];for(let t=0,n=r.length;t<n;t++)r[t].isDataTexture?e.push(rs(r[t].image)):e.push(rs(r[t]))}else e=rs(r);n.url=e}return t||(e.images[this.uuid]=n),n}};function rs(e){return typeof HTMLImageElement<`u`&&e instanceof HTMLImageElement||typeof HTMLCanvasElement<`u`&&e instanceof HTMLCanvasElement||typeof ImageBitmap<`u`&&e instanceof ImageBitmap?es.getDataURL(e):e.data?{data:Array.from(e.data),width:e.width,height:e.height,type:e.data.constructor.name}:(R(`Texture: Unable to serialize Texture.`),{})}var is=0,as=new H,os=class e extends go{constructor(t=e.DEFAULT_IMAGE,n=e.DEFAULT_MAPPING,r=ki,i=ki,a=Pi,o=Ii,s=Qi,c=Li,l=e.DEFAULT_ANISOTROPY,u=``){super(),this.isTexture=!0,Object.defineProperty(this,"id",{value:is++}),this.uuid=xo(),this.name=``,this.source=new ns(t),this.mipmaps=[],this.mapping=n,this.channel=0,this.wrapS=r,this.wrapT=i,this.magFilter=a,this.minFilter=o,this.anisotropy=l,this.format=s,this.internalFormat=null,this.type=c,this.offset=new V(0,0),this.repeat=new V(1,1),this.center=new V(0,0),this.rotation=0,this.matrixAutoUpdate=!0,this.matrix=new U,this.generateMipmaps=!0,this.premultiplyAlpha=!1,this.flipY=!0,this.unpackAlignment=4,this.colorSpace=u,this.userData={},this.updateRanges=[],this.version=0,this.onUpdate=null,this.renderTarget=null,this.isRenderTargetTexture=!1,this.isArrayTexture=!!(t&&t.depth&&t.depth>1),this.pmremVersion=0,this.normalized=!1}get width(){return this.source.getSize(as).x}get height(){return this.source.getSize(as).y}get depth(){return this.source.getSize(as).z}get image(){return this.source.data}set image(e){this.source.data=e}updateMatrix(){this.matrix.setUvTransform(this.offset.x,this.offset.y,this.repeat.x,this.repeat.y,this.rotation,this.center.x,this.center.y)}addUpdateRange(e,t){this.updateRanges.push({start:e,count:t})}clearUpdateRanges(){this.updateRanges.length=0}clone(){return new this.constructor().copy(this)}copy(e){return this.name=e.name,this.source=e.source,this.mipmaps=e.mipmaps.slice(0),this.mapping=e.mapping,this.channel=e.channel,this.wrapS=e.wrapS,this.wrapT=e.wrapT,this.magFilter=e.magFilter,this.minFilter=e.minFilter,this.anisotropy=e.anisotropy,this.format=e.format,this.internalFormat=e.internalFormat,this.type=e.type,this.normalized=e.normalized,this.offset.copy(e.offset),this.repeat.copy(e.repeat),this.center.copy(e.center),this.rotation=e.rotation,this.matrixAutoUpdate=e.matrixAutoUpdate,this.matrix.copy(e.matrix),this.generateMipmaps=e.generateMipmaps,this.premultiplyAlpha=e.premultiplyAlpha,this.flipY=e.flipY,this.unpackAlignment=e.unpackAlignment,this.colorSpace=e.colorSpace,this.renderTarget=e.renderTarget,this.isRenderTargetTexture=e.isRenderTargetTexture,this.isArrayTexture=e.isArrayTexture,this.userData=JSON.parse(JSON.stringify(e.userData)),this.needsUpdate=!0,this}setValues(e){for(let t in e){let n=e[t];if(n===void 0){R(`Texture.setValues(): parameter '${t}' has value of undefined.`);continue}let r=this[t];if(r===void 0){R(`Texture.setValues(): property '${t}' does not exist.`);continue}r&&n&&r.isVector2&&n.isVector2||r&&n&&r.isVector3&&n.isVector3||r&&n&&r.isMatrix3&&n.isMatrix3?r.copy(n):this[t]=n}}toJSON(e){let t=e===void 0||typeof e==`string`;if(!t&&e.textures[this.uuid]!==void 0)return e.textures[this.uuid];let n={metadata:{version:4.7,type:`Texture`,generator:`Texture.toJSON`},uuid:this.uuid,name:this.name,image:this.source.toJSON(e).uuid,mapping:this.mapping,channel:this.channel,repeat:[this.repeat.x,this.repeat.y],offset:[this.offset.x,this.offset.y],center:[this.center.x,this.center.y],rotation:this.rotation,wrap:[this.wrapS,this.wrapT],format:this.format,internalFormat:this.internalFormat,type:this.type,normalized:this.normalized,colorSpace:this.colorSpace,minFilter:this.minFilter,magFilter:this.magFilter,anisotropy:this.anisotropy,flipY:this.flipY,generateMipmaps:this.generateMipmaps,premultiplyAlpha:this.premultiplyAlpha,unpackAlignment:this.unpackAlignment};return Object.keys(this.userData).length>0&&(n.userData=this.userData),t||(e.textures[this.uuid]=n),n}dispose(){this.dispatchEvent({type:`dispose`})}transformUv(e){if(this.mapping!==300)return e;if(e.applyMatrix3(this.matrix),e.x<0||e.x>1)switch(this.wrapS){case Oi:e.x-=Math.floor(e.x);break;case ki:e.x=e.x<0?0:1;break;case Ai:Math.abs(Math.floor(e.x)%2)===1?e.x=Math.ceil(e.x)-e.x:e.x-=Math.floor(e.x);break}if(e.y<0||e.y>1)switch(this.wrapT){case Oi:e.y-=Math.floor(e.y);break;case ki:e.y=e.y<0?0:1;break;case Ai:Math.abs(Math.floor(e.y)%2)===1?e.y=Math.ceil(e.y)-e.y:e.y-=Math.floor(e.y);break}return this.flipY&&(e.y=1-e.y),e}set needsUpdate(e){e===!0&&(this.version++,this.source.needsUpdate=!0)}set needsPMREMUpdate(e){e===!0&&this.pmremVersion++}};os.DEFAULT_IMAGE=null,os.DEFAULT_MAPPING=300,os.DEFAULT_ANISOTROPY=1;var ss=class e{static{e.prototype.isVector4=!0}constructor(e=0,t=0,n=0,r=1){this.x=e,this.y=t,this.z=n,this.w=r}get width(){return this.z}set width(e){this.z=e}get height(){return this.w}set height(e){this.w=e}set(e,t,n,r){return this.x=e,this.y=t,this.z=n,this.w=r,this}setScalar(e){return this.x=e,this.y=e,this.z=e,this.w=e,this}setX(e){return this.x=e,this}setY(e){return this.y=e,this}setZ(e){return this.z=e,this}setW(e){return this.w=e,this}setComponent(e,t){switch(e){case 0:this.x=t;break;case 1:this.y=t;break;case 2:this.z=t;break;case 3:this.w=t;break;default:throw Error(`index is out of range: `+e)}return this}getComponent(e){switch(e){case 0:return this.x;case 1:return this.y;case 2:return this.z;case 3:return this.w;default:throw Error(`index is out of range: `+e)}}clone(){return new this.constructor(this.x,this.y,this.z,this.w)}copy(e){return this.x=e.x,this.y=e.y,this.z=e.z,this.w=e.w===void 0?1:e.w,this}add(e){return this.x+=e.x,this.y+=e.y,this.z+=e.z,this.w+=e.w,this}addScalar(e){return this.x+=e,this.y+=e,this.z+=e,this.w+=e,this}addVectors(e,t){return this.x=e.x+t.x,this.y=e.y+t.y,this.z=e.z+t.z,this.w=e.w+t.w,this}addScaledVector(e,t){return this.x+=e.x*t,this.y+=e.y*t,this.z+=e.z*t,this.w+=e.w*t,this}sub(e){return this.x-=e.x,this.y-=e.y,this.z-=e.z,this.w-=e.w,this}subScalar(e){return this.x-=e,this.y-=e,this.z-=e,this.w-=e,this}subVectors(e,t){return this.x=e.x-t.x,this.y=e.y-t.y,this.z=e.z-t.z,this.w=e.w-t.w,this}multiply(e){return this.x*=e.x,this.y*=e.y,this.z*=e.z,this.w*=e.w,this}multiplyScalar(e){return this.x*=e,this.y*=e,this.z*=e,this.w*=e,this}applyMatrix4(e){let t=this.x,n=this.y,r=this.z,i=this.w,a=e.elements;return this.x=a[0]*t+a[4]*n+a[8]*r+a[12]*i,this.y=a[1]*t+a[5]*n+a[9]*r+a[13]*i,this.z=a[2]*t+a[6]*n+a[10]*r+a[14]*i,this.w=a[3]*t+a[7]*n+a[11]*r+a[15]*i,this}divide(e){return this.x/=e.x,this.y/=e.y,this.z/=e.z,this.w/=e.w,this}divideScalar(e){return this.multiplyScalar(1/e)}setAxisAngleFromQuaternion(e){this.w=2*Math.acos(e.w);let t=Math.sqrt(1-e.w*e.w);return t<1e-4?(this.x=1,this.y=0,this.z=0):(this.x=e.x/t,this.y=e.y/t,this.z=e.z/t),this}setAxisAngleFromRotationMatrix(e){let t,n,r,i,a=.01,o=.1,s=e.elements,c=s[0],l=s[4],u=s[8],d=s[1],f=s[5],p=s[9],m=s[2],h=s[6],g=s[10];if(Math.abs(l-d)<a&&Math.abs(u-m)<a&&Math.abs(p-h)<a){if(Math.abs(l+d)<o&&Math.abs(u+m)<o&&Math.abs(p+h)<o&&Math.abs(c+f+g-3)<o)return this.set(1,0,0,0),this;t=Math.PI;let e=(c+1)/2,s=(f+1)/2,_=(g+1)/2,v=(l+d)/4,y=(u+m)/4,b=(p+h)/4;return e>s&&e>_?e<a?(n=0,r=.707106781,i=.707106781):(n=Math.sqrt(e),r=v/n,i=y/n):s>_?s<a?(n=.707106781,r=0,i=.707106781):(r=Math.sqrt(s),n=v/r,i=b/r):_<a?(n=.707106781,r=.707106781,i=0):(i=Math.sqrt(_),n=y/i,r=b/i),this.set(n,r,i,t),this}let _=Math.sqrt((h-p)*(h-p)+(u-m)*(u-m)+(d-l)*(d-l));return Math.abs(_)<.001&&(_=1),this.x=(h-p)/_,this.y=(u-m)/_,this.z=(d-l)/_,this.w=Math.acos((c+f+g-1)/2),this}setFromMatrixPosition(e){let t=e.elements;return this.x=t[12],this.y=t[13],this.z=t[14],this.w=t[15],this}min(e){return this.x=Math.min(this.x,e.x),this.y=Math.min(this.y,e.y),this.z=Math.min(this.z,e.z),this.w=Math.min(this.w,e.w),this}max(e){return this.x=Math.max(this.x,e.x),this.y=Math.max(this.y,e.y),this.z=Math.max(this.z,e.z),this.w=Math.max(this.w,e.w),this}clamp(e,t){return this.x=B(this.x,e.x,t.x),this.y=B(this.y,e.y,t.y),this.z=B(this.z,e.z,t.z),this.w=B(this.w,e.w,t.w),this}clampScalar(e,t){return this.x=B(this.x,e,t),this.y=B(this.y,e,t),this.z=B(this.z,e,t),this.w=B(this.w,e,t),this}clampLength(e,t){let n=this.length();return this.divideScalar(n||1).multiplyScalar(B(n,e,t))}floor(){return this.x=Math.floor(this.x),this.y=Math.floor(this.y),this.z=Math.floor(this.z),this.w=Math.floor(this.w),this}ceil(){return this.x=Math.ceil(this.x),this.y=Math.ceil(this.y),this.z=Math.ceil(this.z),this.w=Math.ceil(this.w),this}round(){return this.x=Math.round(this.x),this.y=Math.round(this.y),this.z=Math.round(this.z),this.w=Math.round(this.w),this}roundToZero(){return this.x=Math.trunc(this.x),this.y=Math.trunc(this.y),this.z=Math.trunc(this.z),this.w=Math.trunc(this.w),this}negate(){return this.x=-this.x,this.y=-this.y,this.z=-this.z,this.w=-this.w,this}dot(e){return this.x*e.x+this.y*e.y+this.z*e.z+this.w*e.w}lengthSq(){return this.x*this.x+this.y*this.y+this.z*this.z+this.w*this.w}length(){return Math.sqrt(this.x*this.x+this.y*this.y+this.z*this.z+this.w*this.w)}manhattanLength(){return Math.abs(this.x)+Math.abs(this.y)+Math.abs(this.z)+Math.abs(this.w)}normalize(){return this.divideScalar(this.length()||1)}setLength(e){return this.normalize().multiplyScalar(e)}lerp(e,t){return this.x+=(e.x-this.x)*t,this.y+=(e.y-this.y)*t,this.z+=(e.z-this.z)*t,this.w+=(e.w-this.w)*t,this}lerpVectors(e,t,n){return this.x=e.x+(t.x-e.x)*n,this.y=e.y+(t.y-e.y)*n,this.z=e.z+(t.z-e.z)*n,this.w=e.w+(t.w-e.w)*n,this}equals(e){return e.x===this.x&&e.y===this.y&&e.z===this.z&&e.w===this.w}fromArray(e,t=0){return this.x=e[t],this.y=e[t+1],this.z=e[t+2],this.w=e[t+3],this}toArray(e=[],t=0){return e[t]=this.x,e[t+1]=this.y,e[t+2]=this.z,e[t+3]=this.w,e}fromBufferAttribute(e,t){return this.x=e.getX(t),this.y=e.getY(t),this.z=e.getZ(t),this.w=e.getW(t),this}random(){return this.x=Math.random(),this.y=Math.random(),this.z=Math.random(),this.w=Math.random(),this}*[Symbol.iterator](){yield this.x,yield this.y,yield this.z,yield this.w}},cs=class extends go{constructor(e=1,t=1,n={}){super(),n=Object.assign({generateMipmaps:!1,internalFormat:null,minFilter:Pi,depthBuffer:!0,stencilBuffer:!1,resolveDepthBuffer:!0,resolveStencilBuffer:!0,depthTexture:null,samples:0,count:1,depth:1,multiview:!1},n),this.isRenderTarget=!0,this.width=e,this.height=t,this.depth=n.depth,this.scissor=new ss(0,0,e,t),this.scissorTest=!1,this.viewport=new ss(0,0,e,t),this.textures=[];let r=new os({width:e,height:t,depth:n.depth}),i=n.count;for(let e=0;e<i;e++)this.textures[e]=r.clone(),this.textures[e].isRenderTargetTexture=!0,this.textures[e].renderTarget=this;this._setTextureOptions(n),this.depthBuffer=n.depthBuffer,this.stencilBuffer=n.stencilBuffer,this.resolveDepthBuffer=n.resolveDepthBuffer,this.resolveStencilBuffer=n.resolveStencilBuffer,this._depthTexture=null,this.depthTexture=n.depthTexture,this.samples=n.samples,this.multiview=n.multiview}_setTextureOptions(e={}){let t={minFilter:Pi,generateMipmaps:!1,flipY:!1,internalFormat:null};e.mapping!==void 0&&(t.mapping=e.mapping),e.wrapS!==void 0&&(t.wrapS=e.wrapS),e.wrapT!==void 0&&(t.wrapT=e.wrapT),e.wrapR!==void 0&&(t.wrapR=e.wrapR),e.magFilter!==void 0&&(t.magFilter=e.magFilter),e.minFilter!==void 0&&(t.minFilter=e.minFilter),e.format!==void 0&&(t.format=e.format),e.type!==void 0&&(t.type=e.type),e.anisotropy!==void 0&&(t.anisotropy=e.anisotropy),e.colorSpace!==void 0&&(t.colorSpace=e.colorSpace),e.flipY!==void 0&&(t.flipY=e.flipY),e.generateMipmaps!==void 0&&(t.generateMipmaps=e.generateMipmaps),e.internalFormat!==void 0&&(t.internalFormat=e.internalFormat);for(let e=0;e<this.textures.length;e++)this.textures[e].setValues(t)}get texture(){return this.textures[0]}set texture(e){this.textures[0]=e}set depthTexture(e){this._depthTexture!==null&&(this._depthTexture.renderTarget=null),e!==null&&(e.renderTarget=this),this._depthTexture=e}get depthTexture(){return this._depthTexture}setSize(e,t,n=1){if(this.width!==e||this.height!==t||this.depth!==n){this.width=e,this.height=t,this.depth=n;for(let r=0,i=this.textures.length;r<i;r++)this.textures[r].image.width=e,this.textures[r].image.height=t,this.textures[r].image.depth=n,this.textures[r].isData3DTexture!==!0&&(this.textures[r].isArrayTexture=this.textures[r].image.depth>1);this.dispose()}this.viewport.set(0,0,e,t),this.scissor.set(0,0,e,t)}clone(){return new this.constructor().copy(this)}copy(e){this.width=e.width,this.height=e.height,this.depth=e.depth,this.scissor.copy(e.scissor),this.scissorTest=e.scissorTest,this.viewport.copy(e.viewport),this.textures.length=0;for(let t=0,n=e.textures.length;t<n;t++){this.textures[t]=e.textures[t].clone(),this.textures[t].isRenderTargetTexture=!0,this.textures[t].renderTarget=this;let n=Object.assign({},e.textures[t].image);this.textures[t].source=new ns(n)}return this.depthBuffer=e.depthBuffer,this.stencilBuffer=e.stencilBuffer,this.resolveDepthBuffer=e.resolveDepthBuffer,this.resolveStencilBuffer=e.resolveStencilBuffer,e.depthTexture!==null&&(this.depthTexture=e.depthTexture.clone()),this.samples=e.samples,this.multiview=e.multiview,this}dispose(){this.dispatchEvent({type:`dispose`})}},ls=class extends cs{constructor(e=1,t=1,n={}){super(e,t,n),this.isWebGLRenderTarget=!0}},us=class extends os{constructor(e=null,t=1,n=1,r=1){super(null),this.isDataArrayTexture=!0,this.image={data:e,width:t,height:n,depth:r},this.magFilter=ji,this.minFilter=ji,this.wrapR=ki,this.generateMipmaps=!1,this.flipY=!1,this.unpackAlignment=1,this.layerUpdates=new Set}addLayerUpdate(e){this.layerUpdates.add(e)}clearLayerUpdates(){this.layerUpdates.clear()}},ds=class extends os{constructor(e=null,t=1,n=1,r=1){super(null),this.isData3DTexture=!0,this.image={data:e,width:t,height:n,depth:r},this.magFilter=ji,this.minFilter=ji,this.wrapR=ki,this.generateMipmaps=!1,this.flipY=!1,this.unpackAlignment=1}},fs=class e{static{e.prototype.isMatrix4=!0}constructor(e,t,n,r,i,a,o,s,c,l,u,d,f,p,m,h){this.elements=[1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1],e!==void 0&&this.set(e,t,n,r,i,a,o,s,c,l,u,d,f,p,m,h)}set(e,t,n,r,i,a,o,s,c,l,u,d,f,p,m,h){let g=this.elements;return g[0]=e,g[4]=t,g[8]=n,g[12]=r,g[1]=i,g[5]=a,g[9]=o,g[13]=s,g[2]=c,g[6]=l,g[10]=u,g[14]=d,g[3]=f,g[7]=p,g[11]=m,g[15]=h,this}identity(){return this.set(1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1),this}clone(){return new e().fromArray(this.elements)}copy(e){let t=this.elements,n=e.elements;return t[0]=n[0],t[1]=n[1],t[2]=n[2],t[3]=n[3],t[4]=n[4],t[5]=n[5],t[6]=n[6],t[7]=n[7],t[8]=n[8],t[9]=n[9],t[10]=n[10],t[11]=n[11],t[12]=n[12],t[13]=n[13],t[14]=n[14],t[15]=n[15],this}copyPosition(e){let t=this.elements,n=e.elements;return t[12]=n[12],t[13]=n[13],t[14]=n[14],this}setFromMatrix3(e){let t=e.elements;return this.set(t[0],t[3],t[6],0,t[1],t[4],t[7],0,t[2],t[5],t[8],0,0,0,0,1),this}extractBasis(e,t,n){return this.determinant()===0?(e.set(1,0,0),t.set(0,1,0),n.set(0,0,1),this):(e.setFromMatrixColumn(this,0),t.setFromMatrixColumn(this,1),n.setFromMatrixColumn(this,2),this)}makeBasis(e,t,n){return this.set(e.x,t.x,n.x,0,e.y,t.y,n.y,0,e.z,t.z,n.z,0,0,0,0,1),this}extractRotation(e){if(e.determinant()===0)return this.identity();let t=this.elements,n=e.elements,r=1/ps.setFromMatrixColumn(e,0).length(),i=1/ps.setFromMatrixColumn(e,1).length(),a=1/ps.setFromMatrixColumn(e,2).length();return t[0]=n[0]*r,t[1]=n[1]*r,t[2]=n[2]*r,t[3]=0,t[4]=n[4]*i,t[5]=n[5]*i,t[6]=n[6]*i,t[7]=0,t[8]=n[8]*a,t[9]=n[9]*a,t[10]=n[10]*a,t[11]=0,t[12]=0,t[13]=0,t[14]=0,t[15]=1,this}makeRotationFromEuler(e){let t=this.elements,n=e.x,r=e.y,i=e.z,a=Math.cos(n),o=Math.sin(n),s=Math.cos(r),c=Math.sin(r),l=Math.cos(i),u=Math.sin(i);if(e.order===`XYZ`){let e=a*l,n=a*u,r=o*l,i=o*u;t[0]=s*l,t[4]=-s*u,t[8]=c,t[1]=n+r*c,t[5]=e-i*c,t[9]=-o*s,t[2]=i-e*c,t[6]=r+n*c,t[10]=a*s}else if(e.order===`YXZ`){let e=s*l,n=s*u,r=c*l,i=c*u;t[0]=e+i*o,t[4]=r*o-n,t[8]=a*c,t[1]=a*u,t[5]=a*l,t[9]=-o,t[2]=n*o-r,t[6]=i+e*o,t[10]=a*s}else if(e.order===`ZXY`){let e=s*l,n=s*u,r=c*l,i=c*u;t[0]=e-i*o,t[4]=-a*u,t[8]=r+n*o,t[1]=n+r*o,t[5]=a*l,t[9]=i-e*o,t[2]=-a*c,t[6]=o,t[10]=a*s}else if(e.order===`ZYX`){let e=a*l,n=a*u,r=o*l,i=o*u;t[0]=s*l,t[4]=r*c-n,t[8]=e*c+i,t[1]=s*u,t[5]=i*c+e,t[9]=n*c-r,t[2]=-c,t[6]=o*s,t[10]=a*s}else if(e.order===`YZX`){let e=a*s,n=a*c,r=o*s,i=o*c;t[0]=s*l,t[4]=i-e*u,t[8]=r*u+n,t[1]=u,t[5]=a*l,t[9]=-o*l,t[2]=-c*l,t[6]=n*u+r,t[10]=e-i*u}else if(e.order===`XZY`){let e=a*s,n=a*c,r=o*s,i=o*c;t[0]=s*l,t[4]=-u,t[8]=c*l,t[1]=e*u+i,t[5]=a*l,t[9]=n*u-r,t[2]=r*u-n,t[6]=o*l,t[10]=i*u+e}return t[3]=0,t[7]=0,t[11]=0,t[12]=0,t[13]=0,t[14]=0,t[15]=1,this}makeRotationFromQuaternion(e){return this.compose(hs,e,gs)}lookAt(e,t,n){let r=this.elements;return ys.subVectors(e,t),ys.lengthSq()===0&&(ys.z=1),ys.normalize(),_s.crossVectors(n,ys),_s.lengthSq()===0&&(Math.abs(n.z)===1?ys.x+=1e-4:ys.z+=1e-4,ys.normalize(),_s.crossVectors(n,ys)),_s.normalize(),vs.crossVectors(ys,_s),r[0]=_s.x,r[4]=vs.x,r[8]=ys.x,r[1]=_s.y,r[5]=vs.y,r[9]=ys.y,r[2]=_s.z,r[6]=vs.z,r[10]=ys.z,this}multiply(e){return this.multiplyMatrices(this,e)}premultiply(e){return this.multiplyMatrices(e,this)}multiplyMatrices(e,t){let n=e.elements,r=t.elements,i=this.elements,a=n[0],o=n[4],s=n[8],c=n[12],l=n[1],u=n[5],d=n[9],f=n[13],p=n[2],m=n[6],h=n[10],g=n[14],_=n[3],v=n[7],y=n[11],b=n[15],x=r[0],S=r[4],C=r[8],w=r[12],T=r[1],E=r[5],D=r[9],O=r[13],k=r[2],A=r[6],ee=r[10],te=r[14],j=r[3],ne=r[7],M=r[11],re=r[15];return i[0]=a*x+o*T+s*k+c*j,i[4]=a*S+o*E+s*A+c*ne,i[8]=a*C+o*D+s*ee+c*M,i[12]=a*w+o*O+s*te+c*re,i[1]=l*x+u*T+d*k+f*j,i[5]=l*S+u*E+d*A+f*ne,i[9]=l*C+u*D+d*ee+f*M,i[13]=l*w+u*O+d*te+f*re,i[2]=p*x+m*T+h*k+g*j,i[6]=p*S+m*E+h*A+g*ne,i[10]=p*C+m*D+h*ee+g*M,i[14]=p*w+m*O+h*te+g*re,i[3]=_*x+v*T+y*k+b*j,i[7]=_*S+v*E+y*A+b*ne,i[11]=_*C+v*D+y*ee+b*M,i[15]=_*w+v*O+y*te+b*re,this}multiplyScalar(e){let t=this.elements;return t[0]*=e,t[4]*=e,t[8]*=e,t[12]*=e,t[1]*=e,t[5]*=e,t[9]*=e,t[13]*=e,t[2]*=e,t[6]*=e,t[10]*=e,t[14]*=e,t[3]*=e,t[7]*=e,t[11]*=e,t[15]*=e,this}determinant(){let e=this.elements,t=e[0],n=e[4],r=e[8],i=e[12],a=e[1],o=e[5],s=e[9],c=e[13],l=e[2],u=e[6],d=e[10],f=e[14],p=e[3],m=e[7],h=e[11],g=e[15],_=s*f-c*d,v=o*f-c*u,y=o*d-s*u,b=a*f-c*l,x=a*d-s*l,S=a*u-o*l;return t*(m*_-h*v+g*y)-n*(p*_-h*b+g*x)+r*(p*v-m*b+g*S)-i*(p*y-m*x+h*S)}transpose(){let e=this.elements,t;return t=e[1],e[1]=e[4],e[4]=t,t=e[2],e[2]=e[8],e[8]=t,t=e[6],e[6]=e[9],e[9]=t,t=e[3],e[3]=e[12],e[12]=t,t=e[7],e[7]=e[13],e[13]=t,t=e[11],e[11]=e[14],e[14]=t,this}setPosition(e,t,n){let r=this.elements;return e.isVector3?(r[12]=e.x,r[13]=e.y,r[14]=e.z):(r[12]=e,r[13]=t,r[14]=n),this}invert(){let e=this.elements,t=e[0],n=e[1],r=e[2],i=e[3],a=e[4],o=e[5],s=e[6],c=e[7],l=e[8],u=e[9],d=e[10],f=e[11],p=e[12],m=e[13],h=e[14],g=e[15],_=t*o-n*a,v=t*s-r*a,y=t*c-i*a,b=n*s-r*o,x=n*c-i*o,S=r*c-i*s,C=l*m-u*p,w=l*h-d*p,T=l*g-f*p,E=u*h-d*m,D=u*g-f*m,O=d*g-f*h,k=_*O-v*D+y*E+b*T-x*w+S*C;if(k===0)return this.set(0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0);let A=1/k;return e[0]=(o*O-s*D+c*E)*A,e[1]=(r*D-n*O-i*E)*A,e[2]=(m*S-h*x+g*b)*A,e[3]=(d*x-u*S-f*b)*A,e[4]=(s*T-a*O-c*w)*A,e[5]=(t*O-r*T+i*w)*A,e[6]=(h*y-p*S-g*v)*A,e[7]=(l*S-d*y+f*v)*A,e[8]=(a*D-o*T+c*C)*A,e[9]=(n*T-t*D-i*C)*A,e[10]=(p*x-m*y+g*_)*A,e[11]=(u*y-l*x-f*_)*A,e[12]=(o*w-a*E-s*C)*A,e[13]=(t*E-n*w+r*C)*A,e[14]=(m*v-p*b-h*_)*A,e[15]=(l*b-u*v+d*_)*A,this}scale(e){let t=this.elements,n=e.x,r=e.y,i=e.z;return t[0]*=n,t[4]*=r,t[8]*=i,t[1]*=n,t[5]*=r,t[9]*=i,t[2]*=n,t[6]*=r,t[10]*=i,t[3]*=n,t[7]*=r,t[11]*=i,this}getMaxScaleOnAxis(){let e=this.elements,t=e[0]*e[0]+e[1]*e[1]+e[2]*e[2],n=e[4]*e[4]+e[5]*e[5]+e[6]*e[6],r=e[8]*e[8]+e[9]*e[9]+e[10]*e[10];return Math.sqrt(Math.max(t,n,r))}makeTranslation(e,t,n){return e.isVector3?this.set(1,0,0,e.x,0,1,0,e.y,0,0,1,e.z,0,0,0,1):this.set(1,0,0,e,0,1,0,t,0,0,1,n,0,0,0,1),this}makeRotationX(e){let t=Math.cos(e),n=Math.sin(e);return this.set(1,0,0,0,0,t,-n,0,0,n,t,0,0,0,0,1),this}makeRotationY(e){let t=Math.cos(e),n=Math.sin(e);return this.set(t,0,n,0,0,1,0,0,-n,0,t,0,0,0,0,1),this}makeRotationZ(e){let t=Math.cos(e),n=Math.sin(e);return this.set(t,-n,0,0,n,t,0,0,0,0,1,0,0,0,0,1),this}makeRotationAxis(e,t){let n=Math.cos(t),r=Math.sin(t),i=1-n,a=e.x,o=e.y,s=e.z,c=i*a,l=i*o;return this.set(c*a+n,c*o-r*s,c*s+r*o,0,c*o+r*s,l*o+n,l*s-r*a,0,c*s-r*o,l*s+r*a,i*s*s+n,0,0,0,0,1),this}makeScale(e,t,n){return this.set(e,0,0,0,0,t,0,0,0,0,n,0,0,0,0,1),this}makeShear(e,t,n,r,i,a){return this.set(1,n,i,0,e,1,a,0,t,r,1,0,0,0,0,1),this}compose(e,t,n){let r=this.elements,i=t._x,a=t._y,o=t._z,s=t._w,c=i+i,l=a+a,u=o+o,d=i*c,f=i*l,p=i*u,m=a*l,h=a*u,g=o*u,_=s*c,v=s*l,y=s*u,b=n.x,x=n.y,S=n.z;return r[0]=(1-(m+g))*b,r[1]=(f+y)*b,r[2]=(p-v)*b,r[3]=0,r[4]=(f-y)*x,r[5]=(1-(d+g))*x,r[6]=(h+_)*x,r[7]=0,r[8]=(p+v)*S,r[9]=(h-_)*S,r[10]=(1-(d+m))*S,r[11]=0,r[12]=e.x,r[13]=e.y,r[14]=e.z,r[15]=1,this}decompose(e,t,n){let r=this.elements;e.x=r[12],e.y=r[13],e.z=r[14];let i=this.determinant();if(i===0)return n.set(1,1,1),t.identity(),this;let a=ps.set(r[0],r[1],r[2]).length(),o=ps.set(r[4],r[5],r[6]).length(),s=ps.set(r[8],r[9],r[10]).length();i<0&&(a=-a),ms.copy(this);let c=1/a,l=1/o,u=1/s;return ms.elements[0]*=c,ms.elements[1]*=c,ms.elements[2]*=c,ms.elements[4]*=l,ms.elements[5]*=l,ms.elements[6]*=l,ms.elements[8]*=u,ms.elements[9]*=u,ms.elements[10]*=u,t.setFromRotationMatrix(ms),n.x=a,n.y=o,n.z=s,this}makePerspective(e,t,n,r,i,a,o=ro,s=!1){let c=this.elements,l=2*i/(t-e),u=2*i/(n-r),d=(t+e)/(t-e),f=(n+r)/(n-r),p,m;if(s)p=i/(a-i),m=a*i/(a-i);else if(o===2e3)p=-(a+i)/(a-i),m=-2*a*i/(a-i);else if(o===2001)p=-a/(a-i),m=-a*i/(a-i);else throw Error(`THREE.Matrix4.makePerspective(): Invalid coordinate system: `+o);return c[0]=l,c[4]=0,c[8]=d,c[12]=0,c[1]=0,c[5]=u,c[9]=f,c[13]=0,c[2]=0,c[6]=0,c[10]=p,c[14]=m,c[3]=0,c[7]=0,c[11]=-1,c[15]=0,this}makeOrthographic(e,t,n,r,i,a,o=ro,s=!1){let c=this.elements,l=2/(t-e),u=2/(n-r),d=-(t+e)/(t-e),f=-(n+r)/(n-r),p,m;if(s)p=1/(a-i),m=a/(a-i);else if(o===2e3)p=-2/(a-i),m=-(a+i)/(a-i);else if(o===2001)p=-1/(a-i),m=-i/(a-i);else throw Error(`THREE.Matrix4.makeOrthographic(): Invalid coordinate system: `+o);return c[0]=l,c[4]=0,c[8]=0,c[12]=d,c[1]=0,c[5]=u,c[9]=0,c[13]=f,c[2]=0,c[6]=0,c[10]=p,c[14]=m,c[3]=0,c[7]=0,c[11]=0,c[15]=1,this}equals(e){let t=this.elements,n=e.elements;for(let e=0;e<16;e++)if(t[e]!==n[e])return!1;return!0}fromArray(e,t=0){for(let n=0;n<16;n++)this.elements[n]=e[n+t];return this}toArray(e=[],t=0){let n=this.elements;return e[t]=n[0],e[t+1]=n[1],e[t+2]=n[2],e[t+3]=n[3],e[t+4]=n[4],e[t+5]=n[5],e[t+6]=n[6],e[t+7]=n[7],e[t+8]=n[8],e[t+9]=n[9],e[t+10]=n[10],e[t+11]=n[11],e[t+12]=n[12],e[t+13]=n[13],e[t+14]=n[14],e[t+15]=n[15],e}},ps=new H,ms=new fs,hs=new H(0,0,0),gs=new H(1,1,1),_s=new H,vs=new H,ys=new H,bs=new fs,xs=new Uo,Ss=class e{constructor(t=0,n=0,r=0,i=e.DEFAULT_ORDER){this.isEuler=!0,this._x=t,this._y=n,this._z=r,this._order=i}get x(){return this._x}set x(e){this._x=e,this._onChangeCallback()}get y(){return this._y}set y(e){this._y=e,this._onChangeCallback()}get z(){return this._z}set z(e){this._z=e,this._onChangeCallback()}get order(){return this._order}set order(e){this._order=e,this._onChangeCallback()}set(e,t,n,r=this._order){return this._x=e,this._y=t,this._z=n,this._order=r,this._onChangeCallback(),this}clone(){return new this.constructor(this._x,this._y,this._z,this._order)}copy(e){return this._x=e._x,this._y=e._y,this._z=e._z,this._order=e._order,this._onChangeCallback(),this}setFromRotationMatrix(e,t=this._order,n=!0){let r=e.elements,i=r[0],a=r[4],o=r[8],s=r[1],c=r[5],l=r[9],u=r[2],d=r[6],f=r[10];switch(t){case`XYZ`:this._y=Math.asin(B(o,-1,1)),Math.abs(o)<.9999999?(this._x=Math.atan2(-l,f),this._z=Math.atan2(-a,i)):(this._x=Math.atan2(d,c),this._z=0);break;case`YXZ`:this._x=Math.asin(-B(l,-1,1)),Math.abs(l)<.9999999?(this._y=Math.atan2(o,f),this._z=Math.atan2(s,c)):(this._y=Math.atan2(-u,i),this._z=0);break;case`ZXY`:this._x=Math.asin(B(d,-1,1)),Math.abs(d)<.9999999?(this._y=Math.atan2(-u,f),this._z=Math.atan2(-a,c)):(this._y=0,this._z=Math.atan2(s,i));break;case`ZYX`:this._y=Math.asin(-B(u,-1,1)),Math.abs(u)<.9999999?(this._x=Math.atan2(d,f),this._z=Math.atan2(s,i)):(this._x=0,this._z=Math.atan2(-a,c));break;case`YZX`:this._z=Math.asin(B(s,-1,1)),Math.abs(s)<.9999999?(this._x=Math.atan2(-l,c),this._y=Math.atan2(-u,i)):(this._x=0,this._y=Math.atan2(o,f));break;case`XZY`:this._z=Math.asin(-B(a,-1,1)),Math.abs(a)<.9999999?(this._x=Math.atan2(d,c),this._y=Math.atan2(o,i)):(this._x=Math.atan2(-l,f),this._y=0);break;default:R(`Euler: .setFromRotationMatrix() encountered an unknown order: `+t)}return this._order=t,n===!0&&this._onChangeCallback(),this}setFromQuaternion(e,t,n){return bs.makeRotationFromQuaternion(e),this.setFromRotationMatrix(bs,t,n)}setFromVector3(e,t=this._order){return this.set(e.x,e.y,e.z,t)}reorder(e){return xs.setFromEuler(this),this.setFromQuaternion(xs,e)}equals(e){return e._x===this._x&&e._y===this._y&&e._z===this._z&&e._order===this._order}fromArray(e){return this._x=e[0],this._y=e[1],this._z=e[2],e[3]!==void 0&&(this._order=e[3]),this._onChangeCallback(),this}toArray(e=[],t=0){return e[t]=this._x,e[t+1]=this._y,e[t+2]=this._z,e[t+3]=this._order,e}_onChange(e){return this._onChangeCallback=e,this}_onChangeCallback(){}*[Symbol.iterator](){yield this._x,yield this._y,yield this._z,yield this._order}};Ss.DEFAULT_ORDER=`XYZ`;var Cs=class{constructor(){this.mask=1}set(e){this.mask=(1<<e|0)>>>0}enable(e){this.mask|=1<<e|0}enableAll(){this.mask=-1}toggle(e){this.mask^=1<<e|0}disable(e){this.mask&=~(1<<e|0)}disableAll(){this.mask=0}test(e){return(this.mask&e.mask)!==0}isEnabled(e){return(this.mask&(1<<e|0))!=0}},ws=0,Ts=new H,Es=new Uo,Ds=new fs,Os=new H,ks=new H,As=new H,js=new Uo,Ms=new H(1,0,0),Ns=new H(0,1,0),Ps=new H(0,0,1),Fs={type:`added`},Is={type:`removed`},Ls={type:`childadded`,child:null},Rs={type:`childremoved`,child:null},zs=class e extends go{constructor(){super(),this.isObject3D=!0,Object.defineProperty(this,"id",{value:ws++}),this.uuid=xo(),this.name=``,this.type=`Object3D`,this.parent=null,this.children=[],this.up=e.DEFAULT_UP.clone();let t=new H,n=new Ss,r=new Uo,i=new H(1,1,1);function a(){r.setFromEuler(n,!1)}function o(){n.setFromQuaternion(r,void 0,!1)}n._onChange(a),r._onChange(o),Object.defineProperties(this,{position:{configurable:!0,enumerable:!0,value:t},rotation:{configurable:!0,enumerable:!0,value:n},quaternion:{configurable:!0,enumerable:!0,value:r},scale:{configurable:!0,enumerable:!0,value:i},modelViewMatrix:{value:new fs},normalMatrix:{value:new U}}),this.matrix=new fs,this.matrixWorld=new fs,this.matrixAutoUpdate=e.DEFAULT_MATRIX_AUTO_UPDATE,this.matrixWorldAutoUpdate=e.DEFAULT_MATRIX_WORLD_AUTO_UPDATE,this.matrixWorldNeedsUpdate=!1,this.layers=new Cs,this.visible=!0,this.castShadow=!1,this.receiveShadow=!1,this.frustumCulled=!0,this.renderOrder=0,this.animations=[],this.customDepthMaterial=void 0,this.customDistanceMaterial=void 0,this.static=!1,this.userData={},this.pivot=null}onBeforeShadow(){}onAfterShadow(){}onBeforeRender(){}onAfterRender(){}applyMatrix4(e){this.matrixAutoUpdate&&this.updateMatrix(),this.matrix.premultiply(e),this.matrix.decompose(this.position,this.quaternion,this.scale)}applyQuaternion(e){return this.quaternion.premultiply(e),this}setRotationFromAxisAngle(e,t){this.quaternion.setFromAxisAngle(e,t)}setRotationFromEuler(e){this.quaternion.setFromEuler(e,!0)}setRotationFromMatrix(e){this.quaternion.setFromRotationMatrix(e)}setRotationFromQuaternion(e){this.quaternion.copy(e)}rotateOnAxis(e,t){return Es.setFromAxisAngle(e,t),this.quaternion.multiply(Es),this}rotateOnWorldAxis(e,t){return Es.setFromAxisAngle(e,t),this.quaternion.premultiply(Es),this}rotateX(e){return this.rotateOnAxis(Ms,e)}rotateY(e){return this.rotateOnAxis(Ns,e)}rotateZ(e){return this.rotateOnAxis(Ps,e)}translateOnAxis(e,t){return Ts.copy(e).applyQuaternion(this.quaternion),this.position.add(Ts.multiplyScalar(t)),this}translateX(e){return this.translateOnAxis(Ms,e)}translateY(e){return this.translateOnAxis(Ns,e)}translateZ(e){return this.translateOnAxis(Ps,e)}localToWorld(e){return this.updateWorldMatrix(!0,!1),e.applyMatrix4(this.matrixWorld)}worldToLocal(e){return this.updateWorldMatrix(!0,!1),e.applyMatrix4(Ds.copy(this.matrixWorld).invert())}lookAt(e,t,n){e.isVector3?Os.copy(e):Os.set(e,t,n);let r=this.parent;this.updateWorldMatrix(!0,!1),ks.setFromMatrixPosition(this.matrixWorld),this.isCamera||this.isLight?Ds.lookAt(ks,Os,this.up):Ds.lookAt(Os,ks,this.up),this.quaternion.setFromRotationMatrix(Ds),r&&(Ds.extractRotation(r.matrixWorld),Es.setFromRotationMatrix(Ds),this.quaternion.premultiply(Es.invert()))}add(e){if(arguments.length>1){for(let e=0;e<arguments.length;e++)this.add(arguments[e]);return this}return e===this?(z(`Object3D.add: object can't be added as a child of itself.`,e),this):(e&&e.isObject3D?(e.removeFromParent(),e.parent=this,this.children.push(e),e.dispatchEvent(Fs),Ls.child=e,this.dispatchEvent(Ls),Ls.child=null):z(`Object3D.add: object not an instance of THREE.Object3D.`,e),this)}remove(e){if(arguments.length>1){for(let e=0;e<arguments.length;e++)this.remove(arguments[e]);return this}let t=this.children.indexOf(e);return t!==-1&&(e.parent=null,this.children.splice(t,1),e.dispatchEvent(Is),Rs.child=e,this.dispatchEvent(Rs),Rs.child=null),this}removeFromParent(){let e=this.parent;return e!==null&&e.remove(this),this}clear(){return this.remove(...this.children)}attach(e){return this.updateWorldMatrix(!0,!1),Ds.copy(this.matrixWorld).invert(),e.parent!==null&&(e.parent.updateWorldMatrix(!0,!1),Ds.multiply(e.parent.matrixWorld)),e.applyMatrix4(Ds),e.removeFromParent(),e.parent=this,this.children.push(e),e.updateWorldMatrix(!1,!0),e.dispatchEvent(Fs),Ls.child=e,this.dispatchEvent(Ls),Ls.child=null,this}getObjectById(e){return this.getObjectByProperty(`id`,e)}getObjectByName(e){return this.getObjectByProperty(`name`,e)}getObjectByProperty(e,t){if(this[e]===t)return this;for(let n=0,r=this.children.length;n<r;n++){let r=this.children[n].getObjectByProperty(e,t);if(r!==void 0)return r}}getObjectsByProperty(e,t,n=[]){this[e]===t&&n.push(this);let r=this.children;for(let i=0,a=r.length;i<a;i++)r[i].getObjectsByProperty(e,t,n);return n}getWorldPosition(e){return this.updateWorldMatrix(!0,!1),e.setFromMatrixPosition(this.matrixWorld)}getWorldQuaternion(e){return this.updateWorldMatrix(!0,!1),this.matrixWorld.decompose(ks,e,As),e}getWorldScale(e){return this.updateWorldMatrix(!0,!1),this.matrixWorld.decompose(ks,js,e),e}getWorldDirection(e){this.updateWorldMatrix(!0,!1);let t=this.matrixWorld.elements;return e.set(t[8],t[9],t[10]).normalize()}raycast(){}traverse(e){e(this);let t=this.children;for(let n=0,r=t.length;n<r;n++)t[n].traverse(e)}traverseVisible(e){if(this.visible===!1)return;e(this);let t=this.children;for(let n=0,r=t.length;n<r;n++)t[n].traverseVisible(e)}traverseAncestors(e){let t=this.parent;t!==null&&(e(t),t.traverseAncestors(e))}updateMatrix(){this.matrix.compose(this.position,this.quaternion,this.scale);let e=this.pivot;if(e!==null){let t=e.x,n=e.y,r=e.z,i=this.matrix.elements;i[12]+=t-i[0]*t-i[4]*n-i[8]*r,i[13]+=n-i[1]*t-i[5]*n-i[9]*r,i[14]+=r-i[2]*t-i[6]*n-i[10]*r}this.matrixWorldNeedsUpdate=!0}updateMatrixWorld(e){this.matrixAutoUpdate&&this.updateMatrix(),(this.matrixWorldNeedsUpdate||e)&&(this.matrixWorldAutoUpdate===!0&&(this.parent===null?this.matrixWorld.copy(this.matrix):this.matrixWorld.multiplyMatrices(this.parent.matrixWorld,this.matrix)),this.matrixWorldNeedsUpdate=!1,e=!0);let t=this.children;for(let n=0,r=t.length;n<r;n++)t[n].updateMatrixWorld(e)}updateWorldMatrix(e,t){let n=this.parent;if(e===!0&&n!==null&&n.updateWorldMatrix(!0,!1),this.matrixAutoUpdate&&this.updateMatrix(),this.matrixWorldAutoUpdate===!0&&(this.parent===null?this.matrixWorld.copy(this.matrix):this.matrixWorld.multiplyMatrices(this.parent.matrixWorld,this.matrix)),t===!0){let e=this.children;for(let t=0,n=e.length;t<n;t++)e[t].updateWorldMatrix(!1,!0)}}toJSON(e){let t=e===void 0||typeof e==`string`,n={};t&&(e={geometries:{},materials:{},textures:{},images:{},shapes:{},skeletons:{},animations:{},nodes:{}},n.metadata={version:4.7,type:`Object`,generator:`Object3D.toJSON`});let r={};r.uuid=this.uuid,r.type=this.type,this.name!==``&&(r.name=this.name),this.castShadow===!0&&(r.castShadow=!0),this.receiveShadow===!0&&(r.receiveShadow=!0),this.visible===!1&&(r.visible=!1),this.frustumCulled===!1&&(r.frustumCulled=!1),this.renderOrder!==0&&(r.renderOrder=this.renderOrder),this.static!==!1&&(r.static=this.static),Object.keys(this.userData).length>0&&(r.userData=this.userData),r.layers=this.layers.mask,r.matrix=this.matrix.toArray(),r.up=this.up.toArray(),this.pivot!==null&&(r.pivot=this.pivot.toArray()),this.matrixAutoUpdate===!1&&(r.matrixAutoUpdate=!1),this.morphTargetDictionary!==void 0&&(r.morphTargetDictionary=Object.assign({},this.morphTargetDictionary)),this.morphTargetInfluences!==void 0&&(r.morphTargetInfluences=this.morphTargetInfluences.slice()),this.isInstancedMesh&&(r.type=`InstancedMesh`,r.count=this.count,r.instanceMatrix=this.instanceMatrix.toJSON(),this.instanceColor!==null&&(r.instanceColor=this.instanceColor.toJSON())),this.isBatchedMesh&&(r.type=`BatchedMesh`,r.perObjectFrustumCulled=this.perObjectFrustumCulled,r.sortObjects=this.sortObjects,r.drawRanges=this._drawRanges,r.reservedRanges=this._reservedRanges,r.geometryInfo=this._geometryInfo.map(e=>({...e,boundingBox:e.boundingBox?e.boundingBox.toJSON():void 0,boundingSphere:e.boundingSphere?e.boundingSphere.toJSON():void 0})),r.instanceInfo=this._instanceInfo.map(e=>({...e})),r.availableInstanceIds=this._availableInstanceIds.slice(),r.availableGeometryIds=this._availableGeometryIds.slice(),r.nextIndexStart=this._nextIndexStart,r.nextVertexStart=this._nextVertexStart,r.geometryCount=this._geometryCount,r.maxInstanceCount=this._maxInstanceCount,r.maxVertexCount=this._maxVertexCount,r.maxIndexCount=this._maxIndexCount,r.geometryInitialized=this._geometryInitialized,r.matricesTexture=this._matricesTexture.toJSON(e),r.indirectTexture=this._indirectTexture.toJSON(e),this._colorsTexture!==null&&(r.colorsTexture=this._colorsTexture.toJSON(e)),this.boundingSphere!==null&&(r.boundingSphere=this.boundingSphere.toJSON()),this.boundingBox!==null&&(r.boundingBox=this.boundingBox.toJSON()));function i(t,n){return t[n.uuid]===void 0&&(t[n.uuid]=n.toJSON(e)),n.uuid}if(this.isScene)this.background&&(this.background.isColor?r.background=this.background.toJSON():this.background.isTexture&&(r.background=this.background.toJSON(e).uuid)),this.environment&&this.environment.isTexture&&this.environment.isRenderTargetTexture!==!0&&(r.environment=this.environment.toJSON(e).uuid);else if(this.isMesh||this.isLine||this.isPoints){r.geometry=i(e.geometries,this.geometry);let t=this.geometry.parameters;if(t!==void 0&&t.shapes!==void 0){let n=t.shapes;if(Array.isArray(n))for(let t=0,r=n.length;t<r;t++){let r=n[t];i(e.shapes,r)}else i(e.shapes,n)}}if(this.isSkinnedMesh&&(r.bindMode=this.bindMode,r.bindMatrix=this.bindMatrix.toArray(),this.skeleton!==void 0&&(i(e.skeletons,this.skeleton),r.skeleton=this.skeleton.uuid)),this.material!==void 0)if(Array.isArray(this.material)){let t=[];for(let n=0,r=this.material.length;n<r;n++)t.push(i(e.materials,this.material[n]));r.material=t}else r.material=i(e.materials,this.material);if(this.children.length>0){r.children=[];for(let t=0;t<this.children.length;t++)r.children.push(this.children[t].toJSON(e).object)}if(this.animations.length>0){r.animations=[];for(let t=0;t<this.animations.length;t++){let n=this.animations[t];r.animations.push(i(e.animations,n))}}if(t){let t=a(e.geometries),r=a(e.materials),i=a(e.textures),o=a(e.images),s=a(e.shapes),c=a(e.skeletons),l=a(e.animations),u=a(e.nodes);t.length>0&&(n.geometries=t),r.length>0&&(n.materials=r),i.length>0&&(n.textures=i),o.length>0&&(n.images=o),s.length>0&&(n.shapes=s),c.length>0&&(n.skeletons=c),l.length>0&&(n.animations=l),u.length>0&&(n.nodes=u)}return n.object=r,n;function a(e){let t=[];for(let n in e){let r=e[n];delete r.metadata,t.push(r)}return t}}clone(e){return new this.constructor().copy(this,e)}copy(e,t=!0){if(this.name=e.name,this.up.copy(e.up),this.position.copy(e.position),this.rotation.order=e.rotation.order,this.quaternion.copy(e.quaternion),this.scale.copy(e.scale),this.pivot=e.pivot===null?null:e.pivot.clone(),this.matrix.copy(e.matrix),this.matrixWorld.copy(e.matrixWorld),this.matrixAutoUpdate=e.matrixAutoUpdate,this.matrixWorldAutoUpdate=e.matrixWorldAutoUpdate,this.matrixWorldNeedsUpdate=e.matrixWorldNeedsUpdate,this.layers.mask=e.layers.mask,this.visible=e.visible,this.castShadow=e.castShadow,this.receiveShadow=e.receiveShadow,this.frustumCulled=e.frustumCulled,this.renderOrder=e.renderOrder,this.static=e.static,this.animations=e.animations.slice(),this.userData=JSON.parse(JSON.stringify(e.userData)),t===!0)for(let t=0;t<e.children.length;t++){let n=e.children[t];this.add(n.clone())}return this}};zs.DEFAULT_UP=new H(0,1,0),zs.DEFAULT_MATRIX_AUTO_UPDATE=!0,zs.DEFAULT_MATRIX_WORLD_AUTO_UPDATE=!0;var Bs=class extends zs{constructor(){super(),this.isGroup=!0,this.type=`Group`}},Vs={type:`move`},Hs=class{constructor(){this._targetRay=null,this._grip=null,this._hand=null}getHandSpace(){return this._hand===null&&(this._hand=new Bs,this._hand.matrixAutoUpdate=!1,this._hand.visible=!1,this._hand.joints={},this._hand.inputState={pinching:!1}),this._hand}getTargetRaySpace(){return this._targetRay===null&&(this._targetRay=new Bs,this._targetRay.matrixAutoUpdate=!1,this._targetRay.visible=!1,this._targetRay.hasLinearVelocity=!1,this._targetRay.linearVelocity=new H,this._targetRay.hasAngularVelocity=!1,this._targetRay.angularVelocity=new H),this._targetRay}getGripSpace(){return this._grip===null&&(this._grip=new Bs,this._grip.matrixAutoUpdate=!1,this._grip.visible=!1,this._grip.hasLinearVelocity=!1,this._grip.linearVelocity=new H,this._grip.hasAngularVelocity=!1,this._grip.angularVelocity=new H,this._grip.eventsEnabled=!1),this._grip}dispatchEvent(e){return this._targetRay!==null&&this._targetRay.dispatchEvent(e),this._grip!==null&&this._grip.dispatchEvent(e),this._hand!==null&&this._hand.dispatchEvent(e),this}connect(e){if(e&&e.hand){let t=this._hand;if(t)for(let n of e.hand.values())this._getHandJoint(t,n)}return this.dispatchEvent({type:`connected`,data:e}),this}disconnect(e){return this.dispatchEvent({type:`disconnected`,data:e}),this._targetRay!==null&&(this._targetRay.visible=!1),this._grip!==null&&(this._grip.visible=!1),this._hand!==null&&(this._hand.visible=!1),this}update(e,t,n){let r=null,i=null,a=null,o=this._targetRay,s=this._grip,c=this._hand;if(e&&t.session.visibilityState!==`visible-blurred`){if(c&&e.hand){a=!0;for(let r of e.hand.values()){let e=t.getJointPose(r,n),i=this._getHandJoint(c,r);e!==null&&(i.matrix.fromArray(e.transform.matrix),i.matrix.decompose(i.position,i.rotation,i.scale),i.matrixWorldNeedsUpdate=!0,i.jointRadius=e.radius),i.visible=e!==null}let r=c.joints[`index-finger-tip`],i=c.joints[`thumb-tip`],o=r.position.distanceTo(i.position);c.inputState.pinching&&o>.025?(c.inputState.pinching=!1,this.dispatchEvent({type:`pinchend`,handedness:e.handedness,target:this})):!c.inputState.pinching&&o<=.015&&(c.inputState.pinching=!0,this.dispatchEvent({type:`pinchstart`,handedness:e.handedness,target:this}))}else s!==null&&e.gripSpace&&(i=t.getPose(e.gripSpace,n),i!==null&&(s.matrix.fromArray(i.transform.matrix),s.matrix.decompose(s.position,s.rotation,s.scale),s.matrixWorldNeedsUpdate=!0,i.linearVelocity?(s.hasLinearVelocity=!0,s.linearVelocity.copy(i.linearVelocity)):s.hasLinearVelocity=!1,i.angularVelocity?(s.hasAngularVelocity=!0,s.angularVelocity.copy(i.angularVelocity)):s.hasAngularVelocity=!1,s.eventsEnabled&&s.dispatchEvent({type:`gripUpdated`,data:e,target:this})));o!==null&&(r=t.getPose(e.targetRaySpace,n),r===null&&i!==null&&(r=i),r!==null&&(o.matrix.fromArray(r.transform.matrix),o.matrix.decompose(o.position,o.rotation,o.scale),o.matrixWorldNeedsUpdate=!0,r.linearVelocity?(o.hasLinearVelocity=!0,o.linearVelocity.copy(r.linearVelocity)):o.hasLinearVelocity=!1,r.angularVelocity?(o.hasAngularVelocity=!0,o.angularVelocity.copy(r.angularVelocity)):o.hasAngularVelocity=!1,this.dispatchEvent(Vs)))}return o!==null&&(o.visible=r!==null),s!==null&&(s.visible=i!==null),c!==null&&(c.visible=a!==null),this}_getHandJoint(e,t){if(e.joints[t.jointName]===void 0){let n=new Bs;n.matrixAutoUpdate=!1,n.visible=!1,e.joints[t.jointName]=n,e.add(n)}return e.joints[t.jointName]}},Us={aliceblue:15792383,antiquewhite:16444375,aqua:65535,aquamarine:8388564,azure:15794175,beige:16119260,bisque:16770244,black:0,blanchedalmond:16772045,blue:255,blueviolet:9055202,brown:10824234,burlywood:14596231,cadetblue:6266528,chartreuse:8388352,chocolate:13789470,coral:16744272,cornflowerblue:6591981,cornsilk:16775388,crimson:14423100,cyan:65535,darkblue:139,darkcyan:35723,darkgoldenrod:12092939,darkgray:11119017,darkgreen:25600,darkgrey:11119017,darkkhaki:12433259,darkmagenta:9109643,darkolivegreen:5597999,darkorange:16747520,darkorchid:10040012,darkred:9109504,darksalmon:15308410,darkseagreen:9419919,darkslateblue:4734347,darkslategray:3100495,darkslategrey:3100495,darkturquoise:52945,darkviolet:9699539,deeppink:16716947,deepskyblue:49151,dimgray:6908265,dimgrey:6908265,dodgerblue:2003199,firebrick:11674146,floralwhite:16775920,forestgreen:2263842,fuchsia:16711935,gainsboro:14474460,ghostwhite:16316671,gold:16766720,goldenrod:14329120,gray:8421504,green:32768,greenyellow:11403055,grey:8421504,honeydew:15794160,hotpink:16738740,indianred:13458524,indigo:4915330,ivory:16777200,khaki:15787660,lavender:15132410,lavenderblush:16773365,lawngreen:8190976,lemonchiffon:16775885,lightblue:11393254,lightcoral:15761536,lightcyan:14745599,lightgoldenrodyellow:16448210,lightgray:13882323,lightgreen:9498256,lightgrey:13882323,lightpink:16758465,lightsalmon:16752762,lightseagreen:2142890,lightskyblue:8900346,lightslategray:7833753,lightslategrey:7833753,lightsteelblue:11584734,lightyellow:16777184,lime:65280,limegreen:3329330,linen:16445670,magenta:16711935,maroon:8388608,mediumaquamarine:6737322,mediumblue:205,mediumorchid:12211667,mediumpurple:9662683,mediumseagreen:3978097,mediumslateblue:8087790,mediumspringgreen:64154,mediumturquoise:4772300,mediumvioletred:13047173,midnightblue:1644912,mintcream:16121850,mistyrose:16770273,moccasin:16770229,navajowhite:16768685,navy:128,oldlace:16643558,olive:8421376,olivedrab:7048739,orange:16753920,orangered:16729344,orchid:14315734,palegoldenrod:15657130,palegreen:10025880,paleturquoise:11529966,palevioletred:14381203,papayawhip:16773077,peachpuff:16767673,peru:13468991,pink:16761035,plum:14524637,powderblue:11591910,purple:8388736,rebeccapurple:6697881,red:16711680,rosybrown:12357519,royalblue:4286945,saddlebrown:9127187,salmon:16416882,sandybrown:16032864,seagreen:3050327,seashell:16774638,sienna:10506797,silver:12632256,skyblue:8900331,slateblue:6970061,slategray:7372944,slategrey:7372944,snow:16775930,springgreen:65407,steelblue:4620980,tan:13808780,teal:32896,thistle:14204888,tomato:16737095,turquoise:4251856,violet:15631086,wheat:16113331,white:16777215,whitesmoke:16119285,yellow:16776960,yellowgreen:10145074},Ws={h:0,s:0,l:0},Gs={h:0,s:0,l:0};function Ks(e,t,n){return n<0&&(n+=1),n>1&&--n,n<1/6?e+(t-e)*6*n:n<1/2?t:n<2/3?e+(t-e)*6*(2/3-n):e}var W=class{constructor(e,t,n){return this.isColor=!0,this.r=1,this.g=1,this.b=1,this.set(e,t,n)}set(e,t,n){if(t===void 0&&n===void 0){let t=e;t&&t.isColor?this.copy(t):typeof t==`number`?this.setHex(t):typeof t==`string`&&this.setStyle(t)}else this.setRGB(e,t,n);return this}setScalar(e){return this.r=e,this.g=e,this.b=e,this}setHex(e,t=Za){return e=Math.floor(e),this.r=(e>>16&255)/255,this.g=(e>>8&255)/255,this.b=(e&255)/255,Xo.colorSpaceToWorking(this,t),this}setRGB(e,t,n,r=Xo.workingColorSpace){return this.r=e,this.g=t,this.b=n,Xo.colorSpaceToWorking(this,r),this}setHSL(e,t,n,r=Xo.workingColorSpace){if(e=So(e,1),t=B(t,0,1),n=B(n,0,1),t===0)this.r=this.g=this.b=n;else{let r=n<=.5?n*(1+t):n+t-n*t,i=2*n-r;this.r=Ks(i,r,e+1/3),this.g=Ks(i,r,e),this.b=Ks(i,r,e-1/3)}return Xo.colorSpaceToWorking(this,r),this}setStyle(e,t=Za){function n(t){t!==void 0&&parseFloat(t)<1&&R(`Color: Alpha component of `+e+` will be ignored.`)}let r;if(r=/^(\w+)\(([^\)]*)\)/.exec(e)){let i,a=r[1],o=r[2];switch(a){case`rgb`:case`rgba`:if(i=/^\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(?:,\s*(\d*\.?\d+)\s*)?$/.exec(o))return n(i[4]),this.setRGB(Math.min(255,parseInt(i[1],10))/255,Math.min(255,parseInt(i[2],10))/255,Math.min(255,parseInt(i[3],10))/255,t);if(i=/^\s*(\d+)\%\s*,\s*(\d+)\%\s*,\s*(\d+)\%\s*(?:,\s*(\d*\.?\d+)\s*)?$/.exec(o))return n(i[4]),this.setRGB(Math.min(100,parseInt(i[1],10))/100,Math.min(100,parseInt(i[2],10))/100,Math.min(100,parseInt(i[3],10))/100,t);break;case`hsl`:case`hsla`:if(i=/^\s*(\d*\.?\d+)\s*,\s*(\d*\.?\d+)\%\s*,\s*(\d*\.?\d+)\%\s*(?:,\s*(\d*\.?\d+)\s*)?$/.exec(o))return n(i[4]),this.setHSL(parseFloat(i[1])/360,parseFloat(i[2])/100,parseFloat(i[3])/100,t);break;default:R(`Color: Unknown color model `+e)}}else if(r=/^\#([A-Fa-f\d]+)$/.exec(e)){let n=r[1],i=n.length;if(i===3)return this.setRGB(parseInt(n.charAt(0),16)/15,parseInt(n.charAt(1),16)/15,parseInt(n.charAt(2),16)/15,t);if(i===6)return this.setHex(parseInt(n,16),t);R(`Color: Invalid hex color `+e)}else if(e&&e.length>0)return this.setColorName(e,t);return this}setColorName(e,t=Za){let n=Us[e.toLowerCase()];return n===void 0?R(`Color: Unknown color `+e):this.setHex(n,t),this}clone(){return new this.constructor(this.r,this.g,this.b)}copy(e){return this.r=e.r,this.g=e.g,this.b=e.b,this}copySRGBToLinear(e){return this.r=Zo(e.r),this.g=Zo(e.g),this.b=Zo(e.b),this}copyLinearToSRGB(e){return this.r=Qo(e.r),this.g=Qo(e.g),this.b=Qo(e.b),this}convertSRGBToLinear(){return this.copySRGBToLinear(this),this}convertLinearToSRGB(){return this.copyLinearToSRGB(this),this}getHex(e=Za){return Xo.workingToColorSpace(qs.copy(this),e),Math.round(B(qs.r*255,0,255))*65536+Math.round(B(qs.g*255,0,255))*256+Math.round(B(qs.b*255,0,255))}getHexString(e=Za){return(`000000`+this.getHex(e).toString(16)).slice(-6)}getHSL(e,t=Xo.workingColorSpace){Xo.workingToColorSpace(qs.copy(this),t);let n=qs.r,r=qs.g,i=qs.b,a=Math.max(n,r,i),o=Math.min(n,r,i),s,c,l=(o+a)/2;if(o===a)s=0,c=0;else{let e=a-o;switch(c=l<=.5?e/(a+o):e/(2-a-o),a){case n:s=(r-i)/e+(r<i?6:0);break;case r:s=(i-n)/e+2;break;case i:s=(n-r)/e+4;break}s/=6}return e.h=s,e.s=c,e.l=l,e}getRGB(e,t=Xo.workingColorSpace){return Xo.workingToColorSpace(qs.copy(this),t),e.r=qs.r,e.g=qs.g,e.b=qs.b,e}getStyle(e=Za){Xo.workingToColorSpace(qs.copy(this),e);let t=qs.r,n=qs.g,r=qs.b;return e===`srgb`?`rgb(${Math.round(t*255)},${Math.round(n*255)},${Math.round(r*255)})`:`color(${e} ${t.toFixed(3)} ${n.toFixed(3)} ${r.toFixed(3)})`}offsetHSL(e,t,n){return this.getHSL(Ws),this.setHSL(Ws.h+e,Ws.s+t,Ws.l+n)}add(e){return this.r+=e.r,this.g+=e.g,this.b+=e.b,this}addColors(e,t){return this.r=e.r+t.r,this.g=e.g+t.g,this.b=e.b+t.b,this}addScalar(e){return this.r+=e,this.g+=e,this.b+=e,this}sub(e){return this.r=Math.max(0,this.r-e.r),this.g=Math.max(0,this.g-e.g),this.b=Math.max(0,this.b-e.b),this}multiply(e){return this.r*=e.r,this.g*=e.g,this.b*=e.b,this}multiplyScalar(e){return this.r*=e,this.g*=e,this.b*=e,this}lerp(e,t){return this.r+=(e.r-this.r)*t,this.g+=(e.g-this.g)*t,this.b+=(e.b-this.b)*t,this}lerpColors(e,t,n){return this.r=e.r+(t.r-e.r)*n,this.g=e.g+(t.g-e.g)*n,this.b=e.b+(t.b-e.b)*n,this}lerpHSL(e,t){this.getHSL(Ws),e.getHSL(Gs);let n=To(Ws.h,Gs.h,t),r=To(Ws.s,Gs.s,t),i=To(Ws.l,Gs.l,t);return this.setHSL(n,r,i),this}setFromVector3(e){return this.r=e.x,this.g=e.y,this.b=e.z,this}applyMatrix3(e){let t=this.r,n=this.g,r=this.b,i=e.elements;return this.r=i[0]*t+i[3]*n+i[6]*r,this.g=i[1]*t+i[4]*n+i[7]*r,this.b=i[2]*t+i[5]*n+i[8]*r,this}equals(e){return e.r===this.r&&e.g===this.g&&e.b===this.b}fromArray(e,t=0){return this.r=e[t],this.g=e[t+1],this.b=e[t+2],this}toArray(e=[],t=0){return e[t]=this.r,e[t+1]=this.g,e[t+2]=this.b,e}fromBufferAttribute(e,t){return this.r=e.getX(t),this.g=e.getY(t),this.b=e.getZ(t),this}toJSON(){return this.getHex()}*[Symbol.iterator](){yield this.r,yield this.g,yield this.b}},qs=new W;W.NAMES=Us;var Js=class extends zs{constructor(){super(),this.isScene=!0,this.type=`Scene`,this.background=null,this.environment=null,this.fog=null,this.backgroundBlurriness=0,this.backgroundIntensity=1,this.backgroundRotation=new Ss,this.environmentIntensity=1,this.environmentRotation=new Ss,this.overrideMaterial=null,typeof __THREE_DEVTOOLS__<`u`&&__THREE_DEVTOOLS__.dispatchEvent(new CustomEvent(`observe`,{detail:this}))}copy(e,t){return super.copy(e,t),e.background!==null&&(this.background=e.background.clone()),e.environment!==null&&(this.environment=e.environment.clone()),e.fog!==null&&(this.fog=e.fog.clone()),this.backgroundBlurriness=e.backgroundBlurriness,this.backgroundIntensity=e.backgroundIntensity,this.backgroundRotation.copy(e.backgroundRotation),this.environmentIntensity=e.environmentIntensity,this.environmentRotation.copy(e.environmentRotation),e.overrideMaterial!==null&&(this.overrideMaterial=e.overrideMaterial.clone()),this.matrixAutoUpdate=e.matrixAutoUpdate,this}toJSON(e){let t=super.toJSON(e);return this.fog!==null&&(t.object.fog=this.fog.toJSON()),this.backgroundBlurriness>0&&(t.object.backgroundBlurriness=this.backgroundBlurriness),this.backgroundIntensity!==1&&(t.object.backgroundIntensity=this.backgroundIntensity),t.object.backgroundRotation=this.backgroundRotation.toArray(),this.environmentIntensity!==1&&(t.object.environmentIntensity=this.environmentIntensity),t.object.environmentRotation=this.environmentRotation.toArray(),t}},Ys=new H,Xs=new H,Zs=new H,Qs=new H,$s=new H,ec=new H,tc=new H,nc=new H,rc=new H,ic=new H,ac=new ss,oc=new ss,sc=new ss,cc=class e{constructor(e=new H,t=new H,n=new H){this.a=e,this.b=t,this.c=n}static getNormal(e,t,n,r){r.subVectors(n,t),Ys.subVectors(e,t),r.cross(Ys);let i=r.lengthSq();return i>0?r.multiplyScalar(1/Math.sqrt(i)):r.set(0,0,0)}static getBarycoord(e,t,n,r,i){Ys.subVectors(r,t),Xs.subVectors(n,t),Zs.subVectors(e,t);let a=Ys.dot(Ys),o=Ys.dot(Xs),s=Ys.dot(Zs),c=Xs.dot(Xs),l=Xs.dot(Zs),u=a*c-o*o;if(u===0)return i.set(0,0,0),null;let d=1/u,f=(c*s-o*l)*d,p=(a*l-o*s)*d;return i.set(1-f-p,p,f)}static containsPoint(e,t,n,r){return this.getBarycoord(e,t,n,r,Qs)===null?!1:Qs.x>=0&&Qs.y>=0&&Qs.x+Qs.y<=1}static getInterpolation(e,t,n,r,i,a,o,s){return this.getBarycoord(e,t,n,r,Qs)===null?(s.x=0,s.y=0,`z`in s&&(s.z=0),`w`in s&&(s.w=0),null):(s.setScalar(0),s.addScaledVector(i,Qs.x),s.addScaledVector(a,Qs.y),s.addScaledVector(o,Qs.z),s)}static getInterpolatedAttribute(e,t,n,r,i,a){return ac.setScalar(0),oc.setScalar(0),sc.setScalar(0),ac.fromBufferAttribute(e,t),oc.fromBufferAttribute(e,n),sc.fromBufferAttribute(e,r),a.setScalar(0),a.addScaledVector(ac,i.x),a.addScaledVector(oc,i.y),a.addScaledVector(sc,i.z),a}static isFrontFacing(e,t,n,r){return Ys.subVectors(n,t),Xs.subVectors(e,t),Ys.cross(Xs).dot(r)<0}set(e,t,n){return this.a.copy(e),this.b.copy(t),this.c.copy(n),this}setFromPointsAndIndices(e,t,n,r){return this.a.copy(e[t]),this.b.copy(e[n]),this.c.copy(e[r]),this}setFromAttributeAndIndices(e,t,n,r){return this.a.fromBufferAttribute(e,t),this.b.fromBufferAttribute(e,n),this.c.fromBufferAttribute(e,r),this}clone(){return new this.constructor().copy(this)}copy(e){return this.a.copy(e.a),this.b.copy(e.b),this.c.copy(e.c),this}getArea(){return Ys.subVectors(this.c,this.b),Xs.subVectors(this.a,this.b),Ys.cross(Xs).length()*.5}getMidpoint(e){return e.addVectors(this.a,this.b).add(this.c).multiplyScalar(1/3)}getNormal(t){return e.getNormal(this.a,this.b,this.c,t)}getPlane(e){return e.setFromCoplanarPoints(this.a,this.b,this.c)}getBarycoord(t,n){return e.getBarycoord(t,this.a,this.b,this.c,n)}getInterpolation(t,n,r,i,a){return e.getInterpolation(t,this.a,this.b,this.c,n,r,i,a)}containsPoint(t){return e.containsPoint(t,this.a,this.b,this.c)}isFrontFacing(t){return e.isFrontFacing(this.a,this.b,this.c,t)}intersectsBox(e){return e.intersectsTriangle(this)}closestPointToPoint(e,t){let n=this.a,r=this.b,i=this.c,a,o;$s.subVectors(r,n),ec.subVectors(i,n),nc.subVectors(e,n);let s=$s.dot(nc),c=ec.dot(nc);if(s<=0&&c<=0)return t.copy(n);rc.subVectors(e,r);let l=$s.dot(rc),u=ec.dot(rc);if(l>=0&&u<=l)return t.copy(r);let d=s*u-l*c;if(d<=0&&s>=0&&l<=0)return a=s/(s-l),t.copy(n).addScaledVector($s,a);ic.subVectors(e,i);let f=$s.dot(ic),p=ec.dot(ic);if(p>=0&&f<=p)return t.copy(i);let m=f*c-s*p;if(m<=0&&c>=0&&p<=0)return o=c/(c-p),t.copy(n).addScaledVector(ec,o);let h=l*p-f*u;if(h<=0&&u-l>=0&&f-p>=0)return tc.subVectors(i,r),o=(u-l)/(u-l+(f-p)),t.copy(r).addScaledVector(tc,o);let g=1/(h+m+d);return a=m*g,o=d*g,t.copy(n).addScaledVector($s,a).addScaledVector(ec,o)}equals(e){return e.a.equals(this.a)&&e.b.equals(this.b)&&e.c.equals(this.c)}},lc=class{constructor(e=new H(1/0,1/0,1/0),t=new H(-1/0,-1/0,-1/0)){this.isBox3=!0,this.min=e,this.max=t}set(e,t){return this.min.copy(e),this.max.copy(t),this}setFromArray(e){this.makeEmpty();for(let t=0,n=e.length;t<n;t+=3)this.expandByPoint(dc.fromArray(e,t));return this}setFromBufferAttribute(e){this.makeEmpty();for(let t=0,n=e.count;t<n;t++)this.expandByPoint(dc.fromBufferAttribute(e,t));return this}setFromPoints(e){this.makeEmpty();for(let t=0,n=e.length;t<n;t++)this.expandByPoint(e[t]);return this}setFromCenterAndSize(e,t){let n=dc.copy(t).multiplyScalar(.5);return this.min.copy(e).sub(n),this.max.copy(e).add(n),this}setFromObject(e,t=!1){return this.makeEmpty(),this.expandByObject(e,t)}clone(){return new this.constructor().copy(this)}copy(e){return this.min.copy(e.min),this.max.copy(e.max),this}makeEmpty(){return this.min.x=this.min.y=this.min.z=1/0,this.max.x=this.max.y=this.max.z=-1/0,this}isEmpty(){return this.max.x<this.min.x||this.max.y<this.min.y||this.max.z<this.min.z}getCenter(e){return this.isEmpty()?e.set(0,0,0):e.addVectors(this.min,this.max).multiplyScalar(.5)}getSize(e){return this.isEmpty()?e.set(0,0,0):e.subVectors(this.max,this.min)}expandByPoint(e){return this.min.min(e),this.max.max(e),this}expandByVector(e){return this.min.sub(e),this.max.add(e),this}expandByScalar(e){return this.min.addScalar(-e),this.max.addScalar(e),this}expandByObject(e,t=!1){e.updateWorldMatrix(!1,!1);let n=e.geometry;if(n!==void 0){let r=n.getAttribute(`position`);if(t===!0&&r!==void 0&&e.isInstancedMesh!==!0)for(let t=0,n=r.count;t<n;t++)e.isMesh===!0?e.getVertexPosition(t,dc):dc.fromBufferAttribute(r,t),dc.applyMatrix4(e.matrixWorld),this.expandByPoint(dc);else e.boundingBox===void 0?(n.boundingBox===null&&n.computeBoundingBox(),fc.copy(n.boundingBox)):(e.boundingBox===null&&e.computeBoundingBox(),fc.copy(e.boundingBox)),fc.applyMatrix4(e.matrixWorld),this.union(fc)}let r=e.children;for(let e=0,n=r.length;e<n;e++)this.expandByObject(r[e],t);return this}containsPoint(e){return e.x>=this.min.x&&e.x<=this.max.x&&e.y>=this.min.y&&e.y<=this.max.y&&e.z>=this.min.z&&e.z<=this.max.z}containsBox(e){return this.min.x<=e.min.x&&e.max.x<=this.max.x&&this.min.y<=e.min.y&&e.max.y<=this.max.y&&this.min.z<=e.min.z&&e.max.z<=this.max.z}getParameter(e,t){return t.set((e.x-this.min.x)/(this.max.x-this.min.x),(e.y-this.min.y)/(this.max.y-this.min.y),(e.z-this.min.z)/(this.max.z-this.min.z))}intersectsBox(e){return e.max.x>=this.min.x&&e.min.x<=this.max.x&&e.max.y>=this.min.y&&e.min.y<=this.max.y&&e.max.z>=this.min.z&&e.min.z<=this.max.z}intersectsSphere(e){return this.clampPoint(e.center,dc),dc.distanceToSquared(e.center)<=e.radius*e.radius}intersectsPlane(e){let t,n;return e.normal.x>0?(t=e.normal.x*this.min.x,n=e.normal.x*this.max.x):(t=e.normal.x*this.max.x,n=e.normal.x*this.min.x),e.normal.y>0?(t+=e.normal.y*this.min.y,n+=e.normal.y*this.max.y):(t+=e.normal.y*this.max.y,n+=e.normal.y*this.min.y),e.normal.z>0?(t+=e.normal.z*this.min.z,n+=e.normal.z*this.max.z):(t+=e.normal.z*this.max.z,n+=e.normal.z*this.min.z),t<=-e.constant&&n>=-e.constant}intersectsTriangle(e){if(this.isEmpty())return!1;this.getCenter(yc),bc.subVectors(this.max,yc),pc.subVectors(e.a,yc),mc.subVectors(e.b,yc),hc.subVectors(e.c,yc),gc.subVectors(mc,pc),_c.subVectors(hc,mc),vc.subVectors(pc,hc);let t=[0,-gc.z,gc.y,0,-_c.z,_c.y,0,-vc.z,vc.y,gc.z,0,-gc.x,_c.z,0,-_c.x,vc.z,0,-vc.x,-gc.y,gc.x,0,-_c.y,_c.x,0,-vc.y,vc.x,0];return!Cc(t,pc,mc,hc,bc)||(t=[1,0,0,0,1,0,0,0,1],!Cc(t,pc,mc,hc,bc))?!1:(xc.crossVectors(gc,_c),t=[xc.x,xc.y,xc.z],Cc(t,pc,mc,hc,bc))}clampPoint(e,t){return t.copy(e).clamp(this.min,this.max)}distanceToPoint(e){return this.clampPoint(e,dc).distanceTo(e)}getBoundingSphere(e){return this.isEmpty()?e.makeEmpty():(this.getCenter(e.center),e.radius=this.getSize(dc).length()*.5),e}intersect(e){return this.min.max(e.min),this.max.min(e.max),this.isEmpty()&&this.makeEmpty(),this}union(e){return this.min.min(e.min),this.max.max(e.max),this}applyMatrix4(e){return this.isEmpty()?this:(uc[0].set(this.min.x,this.min.y,this.min.z).applyMatrix4(e),uc[1].set(this.min.x,this.min.y,this.max.z).applyMatrix4(e),uc[2].set(this.min.x,this.max.y,this.min.z).applyMatrix4(e),uc[3].set(this.min.x,this.max.y,this.max.z).applyMatrix4(e),uc[4].set(this.max.x,this.min.y,this.min.z).applyMatrix4(e),uc[5].set(this.max.x,this.min.y,this.max.z).applyMatrix4(e),uc[6].set(this.max.x,this.max.y,this.min.z).applyMatrix4(e),uc[7].set(this.max.x,this.max.y,this.max.z).applyMatrix4(e),this.setFromPoints(uc),this)}translate(e){return this.min.add(e),this.max.add(e),this}equals(e){return e.min.equals(this.min)&&e.max.equals(this.max)}toJSON(){return{min:this.min.toArray(),max:this.max.toArray()}}fromJSON(e){return this.min.fromArray(e.min),this.max.fromArray(e.max),this}},uc=[new H,new H,new H,new H,new H,new H,new H,new H],dc=new H,fc=new lc,pc=new H,mc=new H,hc=new H,gc=new H,_c=new H,vc=new H,yc=new H,bc=new H,xc=new H,Sc=new H;function Cc(e,t,n,r,i){for(let a=0,o=e.length-3;a<=o;a+=3){Sc.fromArray(e,a);let o=i.x*Math.abs(Sc.x)+i.y*Math.abs(Sc.y)+i.z*Math.abs(Sc.z),s=t.dot(Sc),c=n.dot(Sc),l=r.dot(Sc);if(Math.max(-Math.max(s,c,l),Math.min(s,c,l))>o)return!1}return!0}var wc=new H,Tc=new V,Ec=0,Dc=class extends go{constructor(e,t,n=!1){if(super(),Array.isArray(e))throw TypeError(`THREE.BufferAttribute: array should be a Typed Array.`);this.isBufferAttribute=!0,Object.defineProperty(this,"id",{value:Ec++}),this.name=``,this.array=e,this.itemSize=t,this.count=e===void 0?0:e.length/t,this.normalized=n,this.usage=no,this.updateRanges=[],this.gpuType=Ui,this.version=0}onUploadCallback(){}set needsUpdate(e){e===!0&&this.version++}setUsage(e){return this.usage=e,this}addUpdateRange(e,t){this.updateRanges.push({start:e,count:t})}clearUpdateRanges(){this.updateRanges.length=0}copy(e){return this.name=e.name,this.array=new e.array.constructor(e.array),this.itemSize=e.itemSize,this.count=e.count,this.normalized=e.normalized,this.usage=e.usage,this.gpuType=e.gpuType,this}copyAt(e,t,n){e*=this.itemSize,n*=t.itemSize;for(let r=0,i=this.itemSize;r<i;r++)this.array[e+r]=t.array[n+r];return this}copyArray(e){return this.array.set(e),this}applyMatrix3(e){if(this.itemSize===2)for(let t=0,n=this.count;t<n;t++)Tc.fromBufferAttribute(this,t),Tc.applyMatrix3(e),this.setXY(t,Tc.x,Tc.y);else if(this.itemSize===3)for(let t=0,n=this.count;t<n;t++)wc.fromBufferAttribute(this,t),wc.applyMatrix3(e),this.setXYZ(t,wc.x,wc.y,wc.z);return this}applyMatrix4(e){for(let t=0,n=this.count;t<n;t++)wc.fromBufferAttribute(this,t),wc.applyMatrix4(e),this.setXYZ(t,wc.x,wc.y,wc.z);return this}applyNormalMatrix(e){for(let t=0,n=this.count;t<n;t++)wc.fromBufferAttribute(this,t),wc.applyNormalMatrix(e),this.setXYZ(t,wc.x,wc.y,wc.z);return this}transformDirection(e){for(let t=0,n=this.count;t<n;t++)wc.fromBufferAttribute(this,t),wc.transformDirection(e),this.setXYZ(t,wc.x,wc.y,wc.z);return this}set(e,t=0){return this.array.set(e,t),this}getComponent(e,t){let n=this.array[e*this.itemSize+t];return this.normalized&&(n=Bo(n,this.array)),n}setComponent(e,t,n){return this.normalized&&(n=Vo(n,this.array)),this.array[e*this.itemSize+t]=n,this}getX(e){let t=this.array[e*this.itemSize];return this.normalized&&(t=Bo(t,this.array)),t}setX(e,t){return this.normalized&&(t=Vo(t,this.array)),this.array[e*this.itemSize]=t,this}getY(e){let t=this.array[e*this.itemSize+1];return this.normalized&&(t=Bo(t,this.array)),t}setY(e,t){return this.normalized&&(t=Vo(t,this.array)),this.array[e*this.itemSize+1]=t,this}getZ(e){let t=this.array[e*this.itemSize+2];return this.normalized&&(t=Bo(t,this.array)),t}setZ(e,t){return this.normalized&&(t=Vo(t,this.array)),this.array[e*this.itemSize+2]=t,this}getW(e){let t=this.array[e*this.itemSize+3];return this.normalized&&(t=Bo(t,this.array)),t}setW(e,t){return this.normalized&&(t=Vo(t,this.array)),this.array[e*this.itemSize+3]=t,this}setXY(e,t,n){return e*=this.itemSize,this.normalized&&(t=Vo(t,this.array),n=Vo(n,this.array)),this.array[e+0]=t,this.array[e+1]=n,this}setXYZ(e,t,n,r){return e*=this.itemSize,this.normalized&&(t=Vo(t,this.array),n=Vo(n,this.array),r=Vo(r,this.array)),this.array[e+0]=t,this.array[e+1]=n,this.array[e+2]=r,this}setXYZW(e,t,n,r,i){return e*=this.itemSize,this.normalized&&(t=Vo(t,this.array),n=Vo(n,this.array),r=Vo(r,this.array),i=Vo(i,this.array)),this.array[e+0]=t,this.array[e+1]=n,this.array[e+2]=r,this.array[e+3]=i,this}onUpload(e){return this.onUploadCallback=e,this}clone(){return new this.constructor(this.array,this.itemSize).copy(this)}toJSON(){let e={itemSize:this.itemSize,type:this.array.constructor.name,array:Array.from(this.array),normalized:this.normalized};return this.name!==``&&(e.name=this.name),this.usage!==35044&&(e.usage=this.usage),e}dispose(){this.dispatchEvent({type:`dispose`})}},Oc=class extends Dc{constructor(e,t,n){super(new Uint16Array(e),t,n)}},kc=class extends Dc{constructor(e,t,n){super(new Uint32Array(e),t,n)}},G=class extends Dc{constructor(e,t,n){super(new Float32Array(e),t,n)}},Ac=new lc,jc=new H,Mc=new H,Nc=class{constructor(e=new H,t=-1){this.isSphere=!0,this.center=e,this.radius=t}set(e,t){return this.center.copy(e),this.radius=t,this}setFromPoints(e,t){let n=this.center;t===void 0?Ac.setFromPoints(e).getCenter(n):n.copy(t);let r=0;for(let t=0,i=e.length;t<i;t++)r=Math.max(r,n.distanceToSquared(e[t]));return this.radius=Math.sqrt(r),this}copy(e){return this.center.copy(e.center),this.radius=e.radius,this}isEmpty(){return this.radius<0}makeEmpty(){return this.center.set(0,0,0),this.radius=-1,this}containsPoint(e){return e.distanceToSquared(this.center)<=this.radius*this.radius}distanceToPoint(e){return e.distanceTo(this.center)-this.radius}intersectsSphere(e){let t=this.radius+e.radius;return e.center.distanceToSquared(this.center)<=t*t}intersectsBox(e){return e.intersectsSphere(this)}intersectsPlane(e){return Math.abs(e.distanceToPoint(this.center))<=this.radius}clampPoint(e,t){let n=this.center.distanceToSquared(e);return t.copy(e),n>this.radius*this.radius&&(t.sub(this.center).normalize(),t.multiplyScalar(this.radius).add(this.center)),t}getBoundingBox(e){return this.isEmpty()?(e.makeEmpty(),e):(e.set(this.center,this.center),e.expandByScalar(this.radius),e)}applyMatrix4(e){return this.center.applyMatrix4(e),this.radius*=e.getMaxScaleOnAxis(),this}translate(e){return this.center.add(e),this}expandByPoint(e){if(this.isEmpty())return this.center.copy(e),this.radius=0,this;jc.subVectors(e,this.center);let t=jc.lengthSq();if(t>this.radius*this.radius){let e=Math.sqrt(t),n=(e-this.radius)*.5;this.center.addScaledVector(jc,n/e),this.radius+=n}return this}union(e){return e.isEmpty()?this:this.isEmpty()?(this.copy(e),this):(this.center.equals(e.center)===!0?this.radius=Math.max(this.radius,e.radius):(Mc.subVectors(e.center,this.center).setLength(e.radius),this.expandByPoint(jc.copy(e.center).add(Mc)),this.expandByPoint(jc.copy(e.center).sub(Mc))),this)}equals(e){return e.center.equals(this.center)&&e.radius===this.radius}clone(){return new this.constructor().copy(this)}toJSON(){return{radius:this.radius,center:this.center.toArray()}}fromJSON(e){return this.radius=e.radius,this.center.fromArray(e.center),this}},Pc=0,Fc=new fs,Ic=new zs,Lc=new H,Rc=new lc,zc=new lc,Bc=new H,Vc=class e extends go{constructor(){super(),this.isBufferGeometry=!0,Object.defineProperty(this,"id",{value:Pc++}),this.uuid=xo(),this.name=``,this.type=`BufferGeometry`,this.index=null,this.indirect=null,this.indirectOffset=0,this.attributes={},this.morphAttributes={},this.morphTargetsRelative=!1,this.groups=[],this.boundingBox=null,this.boundingSphere=null,this.drawRange={start:0,count:1/0},this.userData={}}getIndex(){return this.index}setIndex(e){return Array.isArray(e)?this.index=new(io(e)?kc:Oc)(e,1):this.index=e,this}setIndirect(e,t=0){return this.indirect=e,this.indirectOffset=t,this}getIndirect(){return this.indirect}getAttribute(e){return this.attributes[e]}setAttribute(e,t){return this.attributes[e]=t,this}deleteAttribute(e){return delete this.attributes[e],this}hasAttribute(e){return this.attributes[e]!==void 0}addGroup(e,t,n=0){this.groups.push({start:e,count:t,materialIndex:n})}clearGroups(){this.groups=[]}setDrawRange(e,t){this.drawRange.start=e,this.drawRange.count=t}applyMatrix4(e){let t=this.attributes.position;t!==void 0&&(t.applyMatrix4(e),t.needsUpdate=!0);let n=this.attributes.normal;if(n!==void 0){let t=new U().getNormalMatrix(e);n.applyNormalMatrix(t),n.needsUpdate=!0}let r=this.attributes.tangent;return r!==void 0&&(r.transformDirection(e),r.needsUpdate=!0),this.boundingBox!==null&&this.computeBoundingBox(),this.boundingSphere!==null&&this.computeBoundingSphere(),this}applyQuaternion(e){return Fc.makeRotationFromQuaternion(e),this.applyMatrix4(Fc),this}rotateX(e){return Fc.makeRotationX(e),this.applyMatrix4(Fc),this}rotateY(e){return Fc.makeRotationY(e),this.applyMatrix4(Fc),this}rotateZ(e){return Fc.makeRotationZ(e),this.applyMatrix4(Fc),this}translate(e,t,n){return Fc.makeTranslation(e,t,n),this.applyMatrix4(Fc),this}scale(e,t,n){return Fc.makeScale(e,t,n),this.applyMatrix4(Fc),this}lookAt(e){return Ic.lookAt(e),Ic.updateMatrix(),this.applyMatrix4(Ic.matrix),this}center(){return this.computeBoundingBox(),this.boundingBox.getCenter(Lc).negate(),this.translate(Lc.x,Lc.y,Lc.z),this}setFromPoints(e){let t=this.getAttribute(`position`);if(t===void 0){let t=[];for(let n=0,r=e.length;n<r;n++){let r=e[n];t.push(r.x,r.y,r.z||0)}this.setAttribute(`position`,new G(t,3))}else{let n=Math.min(e.length,t.count);for(let r=0;r<n;r++){let n=e[r];t.setXYZ(r,n.x,n.y,n.z||0)}e.length>t.count&&R(`BufferGeometry: Buffer size too small for points data. Use .dispose() and create a new geometry.`),t.needsUpdate=!0}return this}computeBoundingBox(){this.boundingBox===null&&(this.boundingBox=new lc);let e=this.attributes.position,t=this.morphAttributes.position;if(e&&e.isGLBufferAttribute){z(`BufferGeometry.computeBoundingBox(): GLBufferAttribute requires a manual bounding box.`,this),this.boundingBox.set(new H(-1/0,-1/0,-1/0),new H(1/0,1/0,1/0));return}if(e!==void 0){if(this.boundingBox.setFromBufferAttribute(e),t)for(let e=0,n=t.length;e<n;e++){let n=t[e];Rc.setFromBufferAttribute(n),this.morphTargetsRelative?(Bc.addVectors(this.boundingBox.min,Rc.min),this.boundingBox.expandByPoint(Bc),Bc.addVectors(this.boundingBox.max,Rc.max),this.boundingBox.expandByPoint(Bc)):(this.boundingBox.expandByPoint(Rc.min),this.boundingBox.expandByPoint(Rc.max))}}else this.boundingBox.makeEmpty();(isNaN(this.boundingBox.min.x)||isNaN(this.boundingBox.min.y)||isNaN(this.boundingBox.min.z))&&z(`BufferGeometry.computeBoundingBox(): Computed min/max have NaN values. The "position" attribute is likely to have NaN values.`,this)}computeBoundingSphere(){this.boundingSphere===null&&(this.boundingSphere=new Nc);let e=this.attributes.position,t=this.morphAttributes.position;if(e&&e.isGLBufferAttribute){z(`BufferGeometry.computeBoundingSphere(): GLBufferAttribute requires a manual bounding sphere.`,this),this.boundingSphere.set(new H,1/0);return}if(e){let n=this.boundingSphere.center;if(Rc.setFromBufferAttribute(e),t)for(let e=0,n=t.length;e<n;e++){let n=t[e];zc.setFromBufferAttribute(n),this.morphTargetsRelative?(Bc.addVectors(Rc.min,zc.min),Rc.expandByPoint(Bc),Bc.addVectors(Rc.max,zc.max),Rc.expandByPoint(Bc)):(Rc.expandByPoint(zc.min),Rc.expandByPoint(zc.max))}Rc.getCenter(n);let r=0;for(let t=0,i=e.count;t<i;t++)Bc.fromBufferAttribute(e,t),r=Math.max(r,n.distanceToSquared(Bc));if(t)for(let i=0,a=t.length;i<a;i++){let a=t[i],o=this.morphTargetsRelative;for(let t=0,i=a.count;t<i;t++)Bc.fromBufferAttribute(a,t),o&&(Lc.fromBufferAttribute(e,t),Bc.add(Lc)),r=Math.max(r,n.distanceToSquared(Bc))}this.boundingSphere.radius=Math.sqrt(r),isNaN(this.boundingSphere.radius)&&z(`BufferGeometry.computeBoundingSphere(): Computed radius is NaN. The "position" attribute is likely to have NaN values.`,this)}}computeTangents(){let e=this.index,t=this.attributes;if(e===null||t.position===void 0||t.normal===void 0||t.uv===void 0){z(`BufferGeometry: .computeTangents() failed. Missing required attributes (index, position, normal or uv)`);return}let n=t.position,r=t.normal,i=t.uv;this.hasAttribute(`tangent`)===!1&&this.setAttribute(`tangent`,new Dc(new Float32Array(4*n.count),4));let a=this.getAttribute(`tangent`),o=[],s=[];for(let e=0;e<n.count;e++)o[e]=new H,s[e]=new H;let c=new H,l=new H,u=new H,d=new V,f=new V,p=new V,m=new H,h=new H;function g(e,t,r){c.fromBufferAttribute(n,e),l.fromBufferAttribute(n,t),u.fromBufferAttribute(n,r),d.fromBufferAttribute(i,e),f.fromBufferAttribute(i,t),p.fromBufferAttribute(i,r),l.sub(c),u.sub(c),f.sub(d),p.sub(d);let a=1/(f.x*p.y-p.x*f.y);isFinite(a)&&(m.copy(l).multiplyScalar(p.y).addScaledVector(u,-f.y).multiplyScalar(a),h.copy(u).multiplyScalar(f.x).addScaledVector(l,-p.x).multiplyScalar(a),o[e].add(m),o[t].add(m),o[r].add(m),s[e].add(h),s[t].add(h),s[r].add(h))}let _=this.groups;_.length===0&&(_=[{start:0,count:e.count}]);for(let t=0,n=_.length;t<n;++t){let n=_[t],r=n.start,i=n.count;for(let t=r,n=r+i;t<n;t+=3)g(e.getX(t+0),e.getX(t+1),e.getX(t+2))}let v=new H,y=new H,b=new H,x=new H;function S(e){b.fromBufferAttribute(r,e),x.copy(b);let t=o[e];v.copy(t),v.sub(b.multiplyScalar(b.dot(t))).normalize(),y.crossVectors(x,t);let n=y.dot(s[e])<0?-1:1;a.setXYZW(e,v.x,v.y,v.z,n)}for(let t=0,n=_.length;t<n;++t){let n=_[t],r=n.start,i=n.count;for(let t=r,n=r+i;t<n;t+=3)S(e.getX(t+0)),S(e.getX(t+1)),S(e.getX(t+2))}}computeVertexNormals(){let e=this.index,t=this.getAttribute(`position`);if(t!==void 0){let n=this.getAttribute(`normal`);if(n===void 0)n=new Dc(new Float32Array(t.count*3),3),this.setAttribute(`normal`,n);else for(let e=0,t=n.count;e<t;e++)n.setXYZ(e,0,0,0);let r=new H,i=new H,a=new H,o=new H,s=new H,c=new H,l=new H,u=new H;if(e)for(let d=0,f=e.count;d<f;d+=3){let f=e.getX(d+0),p=e.getX(d+1),m=e.getX(d+2);r.fromBufferAttribute(t,f),i.fromBufferAttribute(t,p),a.fromBufferAttribute(t,m),l.subVectors(a,i),u.subVectors(r,i),l.cross(u),o.fromBufferAttribute(n,f),s.fromBufferAttribute(n,p),c.fromBufferAttribute(n,m),o.add(l),s.add(l),c.add(l),n.setXYZ(f,o.x,o.y,o.z),n.setXYZ(p,s.x,s.y,s.z),n.setXYZ(m,c.x,c.y,c.z)}else for(let e=0,o=t.count;e<o;e+=3)r.fromBufferAttribute(t,e+0),i.fromBufferAttribute(t,e+1),a.fromBufferAttribute(t,e+2),l.subVectors(a,i),u.subVectors(r,i),l.cross(u),n.setXYZ(e+0,l.x,l.y,l.z),n.setXYZ(e+1,l.x,l.y,l.z),n.setXYZ(e+2,l.x,l.y,l.z);this.normalizeNormals(),n.needsUpdate=!0}}normalizeNormals(){let e=this.attributes.normal;for(let t=0,n=e.count;t<n;t++)Bc.fromBufferAttribute(e,t),Bc.normalize(),e.setXYZ(t,Bc.x,Bc.y,Bc.z)}toNonIndexed(){function t(e,t){let n=e.array,r=e.itemSize,i=e.normalized,a=new n.constructor(t.length*r),o=0,s=0;for(let i=0,c=t.length;i<c;i++){o=e.isInterleavedBufferAttribute?t[i]*e.data.stride+e.offset:t[i]*r;for(let e=0;e<r;e++)a[s++]=n[o++]}return new Dc(a,r,i)}if(this.index===null)return R(`BufferGeometry.toNonIndexed(): BufferGeometry is already non-indexed.`),this;let n=new e,r=this.index.array,i=this.attributes;for(let e in i){let a=i[e],o=t(a,r);n.setAttribute(e,o)}let a=this.morphAttributes;for(let e in a){let i=[],o=a[e];for(let e=0,n=o.length;e<n;e++){let n=o[e],a=t(n,r);i.push(a)}n.morphAttributes[e]=i}n.morphTargetsRelative=this.morphTargetsRelative;let o=this.groups;for(let e=0,t=o.length;e<t;e++){let t=o[e];n.addGroup(t.start,t.count,t.materialIndex)}return n}toJSON(){let e={metadata:{version:4.7,type:`BufferGeometry`,generator:`BufferGeometry.toJSON`}};if(e.uuid=this.uuid,e.type=this.type,this.name!==``&&(e.name=this.name),Object.keys(this.userData).length>0&&(e.userData=this.userData),this.parameters!==void 0){let t=this.parameters;for(let n in t)t[n]!==void 0&&(e[n]=t[n]);return e}e.data={attributes:{}};let t=this.index;t!==null&&(e.data.index={type:t.array.constructor.name,array:Array.prototype.slice.call(t.array)});let n=this.attributes;for(let t in n){let r=n[t];e.data.attributes[t]=r.toJSON(e.data)}let r={},i=!1;for(let t in this.morphAttributes){let n=this.morphAttributes[t],a=[];for(let t=0,r=n.length;t<r;t++){let r=n[t];a.push(r.toJSON(e.data))}a.length>0&&(r[t]=a,i=!0)}i&&(e.data.morphAttributes=r,e.data.morphTargetsRelative=this.morphTargetsRelative);let a=this.groups;a.length>0&&(e.data.groups=JSON.parse(JSON.stringify(a)));let o=this.boundingSphere;return o!==null&&(e.data.boundingSphere=o.toJSON()),e}clone(){return new this.constructor().copy(this)}copy(e){this.index=null,this.attributes={},this.morphAttributes={},this.groups=[],this.boundingBox=null,this.boundingSphere=null;let t={};this.name=e.name;let n=e.index;n!==null&&this.setIndex(n.clone());let r=e.attributes;for(let e in r){let n=r[e];this.setAttribute(e,n.clone(t))}let i=e.morphAttributes;for(let e in i){let n=[],r=i[e];for(let e=0,i=r.length;e<i;e++)n.push(r[e].clone(t));this.morphAttributes[e]=n}this.morphTargetsRelative=e.morphTargetsRelative;let a=e.groups;for(let e=0,t=a.length;e<t;e++){let t=a[e];this.addGroup(t.start,t.count,t.materialIndex)}let o=e.boundingBox;o!==null&&(this.boundingBox=o.clone());let s=e.boundingSphere;return s!==null&&(this.boundingSphere=s.clone()),this.drawRange.start=e.drawRange.start,this.drawRange.count=e.drawRange.count,this.userData=e.userData,this}dispose(){this.dispatchEvent({type:`dispose`})}},Hc=class{constructor(e,t){this.isInterleavedBuffer=!0,this.array=e,this.stride=t,this.count=e===void 0?0:e.length/t,this.usage=no,this.updateRanges=[],this.version=0,this.uuid=xo()}onUploadCallback(){}set needsUpdate(e){e===!0&&this.version++}setUsage(e){return this.usage=e,this}addUpdateRange(e,t){this.updateRanges.push({start:e,count:t})}clearUpdateRanges(){this.updateRanges.length=0}copy(e){return this.array=new e.array.constructor(e.array),this.count=e.count,this.stride=e.stride,this.usage=e.usage,this}copyAt(e,t,n){e*=this.stride,n*=t.stride;for(let r=0,i=this.stride;r<i;r++)this.array[e+r]=t.array[n+r];return this}set(e,t=0){return this.array.set(e,t),this}clone(e){e.arrayBuffers===void 0&&(e.arrayBuffers={}),this.array.buffer._uuid===void 0&&(this.array.buffer._uuid=xo()),e.arrayBuffers[this.array.buffer._uuid]===void 0&&(e.arrayBuffers[this.array.buffer._uuid]=this.array.slice(0).buffer);let t=new this.array.constructor(e.arrayBuffers[this.array.buffer._uuid]),n=new this.constructor(t,this.stride);return n.setUsage(this.usage),n}onUpload(e){return this.onUploadCallback=e,this}toJSON(e){return e.arrayBuffers===void 0&&(e.arrayBuffers={}),this.array.buffer._uuid===void 0&&(this.array.buffer._uuid=xo()),e.arrayBuffers[this.array.buffer._uuid]===void 0&&(e.arrayBuffers[this.array.buffer._uuid]=Array.from(new Uint32Array(this.array.buffer))),{uuid:this.uuid,buffer:this.array.buffer._uuid,type:this.array.constructor.name,stride:this.stride}}},Uc=new H,Wc=class e{constructor(e,t,n,r=!1){this.isInterleavedBufferAttribute=!0,this.name=``,this.data=e,this.itemSize=t,this.offset=n,this.normalized=r}get count(){return this.data.count}get array(){return this.data.array}set needsUpdate(e){this.data.needsUpdate=e}applyMatrix4(e){for(let t=0,n=this.data.count;t<n;t++)Uc.fromBufferAttribute(this,t),Uc.applyMatrix4(e),this.setXYZ(t,Uc.x,Uc.y,Uc.z);return this}applyNormalMatrix(e){for(let t=0,n=this.count;t<n;t++)Uc.fromBufferAttribute(this,t),Uc.applyNormalMatrix(e),this.setXYZ(t,Uc.x,Uc.y,Uc.z);return this}transformDirection(e){for(let t=0,n=this.count;t<n;t++)Uc.fromBufferAttribute(this,t),Uc.transformDirection(e),this.setXYZ(t,Uc.x,Uc.y,Uc.z);return this}getComponent(e,t){let n=this.array[e*this.data.stride+this.offset+t];return this.normalized&&(n=Bo(n,this.array)),n}setComponent(e,t,n){return this.normalized&&(n=Vo(n,this.array)),this.data.array[e*this.data.stride+this.offset+t]=n,this}setX(e,t){return this.normalized&&(t=Vo(t,this.array)),this.data.array[e*this.data.stride+this.offset]=t,this}setY(e,t){return this.normalized&&(t=Vo(t,this.array)),this.data.array[e*this.data.stride+this.offset+1]=t,this}setZ(e,t){return this.normalized&&(t=Vo(t,this.array)),this.data.array[e*this.data.stride+this.offset+2]=t,this}setW(e,t){return this.normalized&&(t=Vo(t,this.array)),this.data.array[e*this.data.stride+this.offset+3]=t,this}getX(e){let t=this.data.array[e*this.data.stride+this.offset];return this.normalized&&(t=Bo(t,this.array)),t}getY(e){let t=this.data.array[e*this.data.stride+this.offset+1];return this.normalized&&(t=Bo(t,this.array)),t}getZ(e){let t=this.data.array[e*this.data.stride+this.offset+2];return this.normalized&&(t=Bo(t,this.array)),t}getW(e){let t=this.data.array[e*this.data.stride+this.offset+3];return this.normalized&&(t=Bo(t,this.array)),t}setXY(e,t,n){return e=e*this.data.stride+this.offset,this.normalized&&(t=Vo(t,this.array),n=Vo(n,this.array)),this.data.array[e+0]=t,this.data.array[e+1]=n,this}setXYZ(e,t,n,r){return e=e*this.data.stride+this.offset,this.normalized&&(t=Vo(t,this.array),n=Vo(n,this.array),r=Vo(r,this.array)),this.data.array[e+0]=t,this.data.array[e+1]=n,this.data.array[e+2]=r,this}setXYZW(e,t,n,r,i){return e=e*this.data.stride+this.offset,this.normalized&&(t=Vo(t,this.array),n=Vo(n,this.array),r=Vo(r,this.array),i=Vo(i,this.array)),this.data.array[e+0]=t,this.data.array[e+1]=n,this.data.array[e+2]=r,this.data.array[e+3]=i,this}clone(t){if(t===void 0){uo(`InterleavedBufferAttribute.clone(): Cloning an interleaved buffer attribute will de-interleave buffer data.`);let e=[];for(let t=0;t<this.count;t++){let n=t*this.data.stride+this.offset;for(let t=0;t<this.itemSize;t++)e.push(this.data.array[n+t])}return new Dc(new this.array.constructor(e),this.itemSize,this.normalized)}else return t.interleavedBuffers===void 0&&(t.interleavedBuffers={}),t.interleavedBuffers[this.data.uuid]===void 0&&(t.interleavedBuffers[this.data.uuid]=this.data.clone(t)),new e(t.interleavedBuffers[this.data.uuid],this.itemSize,this.offset,this.normalized)}toJSON(e){if(e===void 0){uo(`InterleavedBufferAttribute.toJSON(): Serializing an interleaved buffer attribute will de-interleave buffer data.`);let e=[];for(let t=0;t<this.count;t++){let n=t*this.data.stride+this.offset;for(let t=0;t<this.itemSize;t++)e.push(this.data.array[n+t])}return{itemSize:this.itemSize,type:this.array.constructor.name,array:e,normalized:this.normalized}}else return e.interleavedBuffers===void 0&&(e.interleavedBuffers={}),e.interleavedBuffers[this.data.uuid]===void 0&&(e.interleavedBuffers[this.data.uuid]=this.data.toJSON(e)),{isInterleavedBufferAttribute:!0,itemSize:this.itemSize,data:this.data.uuid,offset:this.offset,normalized:this.normalized}}},Gc=0,Kc=class extends go{constructor(){super(),this.isMaterial=!0,Object.defineProperty(this,"id",{value:Gc++}),this.uuid=xo(),this.name=``,this.type=`Material`,this.blending=1,this.side=0,this.vertexColors=!1,this.opacity=1,this.transparent=!1,this.alphaHash=!1,this.blendSrc=204,this.blendDst=205,this.blendEquation=100,this.blendSrcAlpha=null,this.blendDstAlpha=null,this.blendEquationAlpha=null,this.blendColor=new W(0,0,0),this.blendAlpha=0,this.depthFunc=3,this.depthTest=!0,this.depthWrite=!0,this.stencilWriteMask=255,this.stencilFunc=519,this.stencilRef=0,this.stencilFuncMask=255,this.stencilFail=to,this.stencilZFail=to,this.stencilZPass=to,this.stencilWrite=!1,this.clippingPlanes=null,this.clipIntersection=!1,this.clipShadows=!1,this.shadowSide=null,this.colorWrite=!0,this.precision=null,this.polygonOffset=!1,this.polygonOffsetFactor=0,this.polygonOffsetUnits=0,this.dithering=!1,this.alphaToCoverage=!1,this.premultipliedAlpha=!1,this.forceSinglePass=!1,this.allowOverride=!0,this.visible=!0,this.toneMapped=!0,this.userData={},this.version=0,this._alphaTest=0}get alphaTest(){return this._alphaTest}set alphaTest(e){this._alphaTest>0!=e>0&&this.version++,this._alphaTest=e}onBeforeRender(){}onBeforeCompile(){}customProgramCacheKey(){return this.onBeforeCompile.toString()}setValues(e){if(e!==void 0)for(let t in e){let n=e[t];if(n===void 0){R(`Material: parameter '${t}' has value of undefined.`);continue}let r=this[t];if(r===void 0){R(`Material: '${t}' is not a property of THREE.${this.type}.`);continue}r&&r.isColor?r.set(n):r&&r.isVector3&&n&&n.isVector3?r.copy(n):this[t]=n}}toJSON(e){let t=e===void 0||typeof e==`string`;t&&(e={textures:{},images:{}});let n={metadata:{version:4.7,type:`Material`,generator:`Material.toJSON`}};n.uuid=this.uuid,n.type=this.type,this.name!==``&&(n.name=this.name),this.color&&this.color.isColor&&(n.color=this.color.getHex()),this.roughness!==void 0&&(n.roughness=this.roughness),this.metalness!==void 0&&(n.metalness=this.metalness),this.sheen!==void 0&&(n.sheen=this.sheen),this.sheenColor&&this.sheenColor.isColor&&(n.sheenColor=this.sheenColor.getHex()),this.sheenRoughness!==void 0&&(n.sheenRoughness=this.sheenRoughness),this.emissive&&this.emissive.isColor&&(n.emissive=this.emissive.getHex()),this.emissiveIntensity!==void 0&&this.emissiveIntensity!==1&&(n.emissiveIntensity=this.emissiveIntensity),this.specular&&this.specular.isColor&&(n.specular=this.specular.getHex()),this.specularIntensity!==void 0&&(n.specularIntensity=this.specularIntensity),this.specularColor&&this.specularColor.isColor&&(n.specularColor=this.specularColor.getHex()),this.shininess!==void 0&&(n.shininess=this.shininess),this.clearcoat!==void 0&&(n.clearcoat=this.clearcoat),this.clearcoatRoughness!==void 0&&(n.clearcoatRoughness=this.clearcoatRoughness),this.clearcoatMap&&this.clearcoatMap.isTexture&&(n.clearcoatMap=this.clearcoatMap.toJSON(e).uuid),this.clearcoatRoughnessMap&&this.clearcoatRoughnessMap.isTexture&&(n.clearcoatRoughnessMap=this.clearcoatRoughnessMap.toJSON(e).uuid),this.clearcoatNormalMap&&this.clearcoatNormalMap.isTexture&&(n.clearcoatNormalMap=this.clearcoatNormalMap.toJSON(e).uuid,n.clearcoatNormalScale=this.clearcoatNormalScale.toArray()),this.sheenColorMap&&this.sheenColorMap.isTexture&&(n.sheenColorMap=this.sheenColorMap.toJSON(e).uuid),this.sheenRoughnessMap&&this.sheenRoughnessMap.isTexture&&(n.sheenRoughnessMap=this.sheenRoughnessMap.toJSON(e).uuid),this.dispersion!==void 0&&(n.dispersion=this.dispersion),this.iridescence!==void 0&&(n.iridescence=this.iridescence),this.iridescenceIOR!==void 0&&(n.iridescenceIOR=this.iridescenceIOR),this.iridescenceThicknessRange!==void 0&&(n.iridescenceThicknessRange=this.iridescenceThicknessRange),this.iridescenceMap&&this.iridescenceMap.isTexture&&(n.iridescenceMap=this.iridescenceMap.toJSON(e).uuid),this.iridescenceThicknessMap&&this.iridescenceThicknessMap.isTexture&&(n.iridescenceThicknessMap=this.iridescenceThicknessMap.toJSON(e).uuid),this.anisotropy!==void 0&&(n.anisotropy=this.anisotropy),this.anisotropyRotation!==void 0&&(n.anisotropyRotation=this.anisotropyRotation),this.anisotropyMap&&this.anisotropyMap.isTexture&&(n.anisotropyMap=this.anisotropyMap.toJSON(e).uuid),this.map&&this.map.isTexture&&(n.map=this.map.toJSON(e).uuid),this.matcap&&this.matcap.isTexture&&(n.matcap=this.matcap.toJSON(e).uuid),this.alphaMap&&this.alphaMap.isTexture&&(n.alphaMap=this.alphaMap.toJSON(e).uuid),this.lightMap&&this.lightMap.isTexture&&(n.lightMap=this.lightMap.toJSON(e).uuid,n.lightMapIntensity=this.lightMapIntensity),this.aoMap&&this.aoMap.isTexture&&(n.aoMap=this.aoMap.toJSON(e).uuid,n.aoMapIntensity=this.aoMapIntensity),this.bumpMap&&this.bumpMap.isTexture&&(n.bumpMap=this.bumpMap.toJSON(e).uuid,n.bumpScale=this.bumpScale),this.normalMap&&this.normalMap.isTexture&&(n.normalMap=this.normalMap.toJSON(e).uuid,n.normalMapType=this.normalMapType,n.normalScale=this.normalScale.toArray()),this.displacementMap&&this.displacementMap.isTexture&&(n.displacementMap=this.displacementMap.toJSON(e).uuid,n.displacementScale=this.displacementScale,n.displacementBias=this.displacementBias),this.roughnessMap&&this.roughnessMap.isTexture&&(n.roughnessMap=this.roughnessMap.toJSON(e).uuid),this.metalnessMap&&this.metalnessMap.isTexture&&(n.metalnessMap=this.metalnessMap.toJSON(e).uuid),this.emissiveMap&&this.emissiveMap.isTexture&&(n.emissiveMap=this.emissiveMap.toJSON(e).uuid),this.specularMap&&this.specularMap.isTexture&&(n.specularMap=this.specularMap.toJSON(e).uuid),this.specularIntensityMap&&this.specularIntensityMap.isTexture&&(n.specularIntensityMap=this.specularIntensityMap.toJSON(e).uuid),this.specularColorMap&&this.specularColorMap.isTexture&&(n.specularColorMap=this.specularColorMap.toJSON(e).uuid),this.envMap&&this.envMap.isTexture&&(n.envMap=this.envMap.toJSON(e).uuid,this.combine!==void 0&&(n.combine=this.combine)),this.envMapRotation!==void 0&&(n.envMapRotation=this.envMapRotation.toArray()),this.envMapIntensity!==void 0&&(n.envMapIntensity=this.envMapIntensity),this.reflectivity!==void 0&&(n.reflectivity=this.reflectivity),this.refractionRatio!==void 0&&(n.refractionRatio=this.refractionRatio),this.gradientMap&&this.gradientMap.isTexture&&(n.gradientMap=this.gradientMap.toJSON(e).uuid),this.transmission!==void 0&&(n.transmission=this.transmission),this.transmissionMap&&this.transmissionMap.isTexture&&(n.transmissionMap=this.transmissionMap.toJSON(e).uuid),this.thickness!==void 0&&(n.thickness=this.thickness),this.thicknessMap&&this.thicknessMap.isTexture&&(n.thicknessMap=this.thicknessMap.toJSON(e).uuid),this.attenuationDistance!==void 0&&this.attenuationDistance!==1/0&&(n.attenuationDistance=this.attenuationDistance),this.attenuationColor!==void 0&&(n.attenuationColor=this.attenuationColor.getHex()),this.size!==void 0&&(n.size=this.size),this.shadowSide!==null&&(n.shadowSide=this.shadowSide),this.sizeAttenuation!==void 0&&(n.sizeAttenuation=this.sizeAttenuation),this.blending!==1&&(n.blending=this.blending),this.side!==0&&(n.side=this.side),this.vertexColors===!0&&(n.vertexColors=!0),this.opacity<1&&(n.opacity=this.opacity),this.transparent===!0&&(n.transparent=!0),this.blendSrc!==204&&(n.blendSrc=this.blendSrc),this.blendDst!==205&&(n.blendDst=this.blendDst),this.blendEquation!==100&&(n.blendEquation=this.blendEquation),this.blendSrcAlpha!==null&&(n.blendSrcAlpha=this.blendSrcAlpha),this.blendDstAlpha!==null&&(n.blendDstAlpha=this.blendDstAlpha),this.blendEquationAlpha!==null&&(n.blendEquationAlpha=this.blendEquationAlpha),this.blendColor&&this.blendColor.isColor&&(n.blendColor=this.blendColor.getHex()),this.blendAlpha!==0&&(n.blendAlpha=this.blendAlpha),this.depthFunc!==3&&(n.depthFunc=this.depthFunc),this.depthTest===!1&&(n.depthTest=this.depthTest),this.depthWrite===!1&&(n.depthWrite=this.depthWrite),this.colorWrite===!1&&(n.colorWrite=this.colorWrite),this.stencilWriteMask!==255&&(n.stencilWriteMask=this.stencilWriteMask),this.stencilFunc!==519&&(n.stencilFunc=this.stencilFunc),this.stencilRef!==0&&(n.stencilRef=this.stencilRef),this.stencilFuncMask!==255&&(n.stencilFuncMask=this.stencilFuncMask),this.stencilFail!==7680&&(n.stencilFail=this.stencilFail),this.stencilZFail!==7680&&(n.stencilZFail=this.stencilZFail),this.stencilZPass!==7680&&(n.stencilZPass=this.stencilZPass),this.stencilWrite===!0&&(n.stencilWrite=this.stencilWrite),this.rotation!==void 0&&this.rotation!==0&&(n.rotation=this.rotation),this.polygonOffset===!0&&(n.polygonOffset=!0),this.polygonOffsetFactor!==0&&(n.polygonOffsetFactor=this.polygonOffsetFactor),this.polygonOffsetUnits!==0&&(n.polygonOffsetUnits=this.polygonOffsetUnits),this.linewidth!==void 0&&this.linewidth!==1&&(n.linewidth=this.linewidth),this.dashSize!==void 0&&(n.dashSize=this.dashSize),this.gapSize!==void 0&&(n.gapSize=this.gapSize),this.scale!==void 0&&(n.scale=this.scale),this.dithering===!0&&(n.dithering=!0),this.alphaTest>0&&(n.alphaTest=this.alphaTest),this.alphaHash===!0&&(n.alphaHash=!0),this.alphaToCoverage===!0&&(n.alphaToCoverage=!0),this.premultipliedAlpha===!0&&(n.premultipliedAlpha=!0),this.forceSinglePass===!0&&(n.forceSinglePass=!0),this.allowOverride===!1&&(n.allowOverride=!1),this.wireframe===!0&&(n.wireframe=!0),this.wireframeLinewidth>1&&(n.wireframeLinewidth=this.wireframeLinewidth),this.wireframeLinecap!==`round`&&(n.wireframeLinecap=this.wireframeLinecap),this.wireframeLinejoin!==`round`&&(n.wireframeLinejoin=this.wireframeLinejoin),this.flatShading===!0&&(n.flatShading=!0),this.visible===!1&&(n.visible=!1),this.toneMapped===!1&&(n.toneMapped=!1),this.fog===!1&&(n.fog=!1),Object.keys(this.userData).length>0&&(n.userData=this.userData);function r(e){let t=[];for(let n in e){let r=e[n];delete r.metadata,t.push(r)}return t}if(t){let t=r(e.textures),i=r(e.images);t.length>0&&(n.textures=t),i.length>0&&(n.images=i)}return n}clone(){return new this.constructor().copy(this)}copy(e){this.name=e.name,this.blending=e.blending,this.side=e.side,this.vertexColors=e.vertexColors,this.opacity=e.opacity,this.transparent=e.transparent,this.blendSrc=e.blendSrc,this.blendDst=e.blendDst,this.blendEquation=e.blendEquation,this.blendSrcAlpha=e.blendSrcAlpha,this.blendDstAlpha=e.blendDstAlpha,this.blendEquationAlpha=e.blendEquationAlpha,this.blendColor.copy(e.blendColor),this.blendAlpha=e.blendAlpha,this.depthFunc=e.depthFunc,this.depthTest=e.depthTest,this.depthWrite=e.depthWrite,this.stencilWriteMask=e.stencilWriteMask,this.stencilFunc=e.stencilFunc,this.stencilRef=e.stencilRef,this.stencilFuncMask=e.stencilFuncMask,this.stencilFail=e.stencilFail,this.stencilZFail=e.stencilZFail,this.stencilZPass=e.stencilZPass,this.stencilWrite=e.stencilWrite;let t=e.clippingPlanes,n=null;if(t!==null){let e=t.length;n=Array(e);for(let r=0;r!==e;++r)n[r]=t[r].clone()}return this.clippingPlanes=n,this.clipIntersection=e.clipIntersection,this.clipShadows=e.clipShadows,this.shadowSide=e.shadowSide,this.colorWrite=e.colorWrite,this.precision=e.precision,this.polygonOffset=e.polygonOffset,this.polygonOffsetFactor=e.polygonOffsetFactor,this.polygonOffsetUnits=e.polygonOffsetUnits,this.dithering=e.dithering,this.alphaTest=e.alphaTest,this.alphaHash=e.alphaHash,this.alphaToCoverage=e.alphaToCoverage,this.premultipliedAlpha=e.premultipliedAlpha,this.forceSinglePass=e.forceSinglePass,this.allowOverride=e.allowOverride,this.visible=e.visible,this.toneMapped=e.toneMapped,this.userData=JSON.parse(JSON.stringify(e.userData)),this}dispose(){this.dispatchEvent({type:`dispose`})}set needsUpdate(e){e===!0&&this.version++}},qc=class extends Kc{constructor(e){super(),this.isSpriteMaterial=!0,this.type=`SpriteMaterial`,this.color=new W(16777215),this.map=null,this.alphaMap=null,this.rotation=0,this.sizeAttenuation=!0,this.transparent=!0,this.fog=!0,this.setValues(e)}copy(e){return super.copy(e),this.color.copy(e.color),this.map=e.map,this.alphaMap=e.alphaMap,this.rotation=e.rotation,this.sizeAttenuation=e.sizeAttenuation,this.fog=e.fog,this}},Jc,Yc=new H,Xc=new H,Zc=new H,Qc=new V,$c=new V,el=new fs,tl=new H,nl=new H,rl=new H,il=new V,al=new V,ol=new V,sl=class extends zs{constructor(e=new qc){if(super(),this.isSprite=!0,this.type=`Sprite`,Jc===void 0){Jc=new Vc;let e=new Hc(new Float32Array([-.5,-.5,0,0,0,.5,-.5,0,1,0,.5,.5,0,1,1,-.5,.5,0,0,1]),5);Jc.setIndex([0,1,2,0,2,3]),Jc.setAttribute(`position`,new Wc(e,3,0,!1)),Jc.setAttribute(`uv`,new Wc(e,2,3,!1))}this.geometry=Jc,this.material=e,this.center=new V(.5,.5),this.count=1}raycast(e,t){e.camera===null&&z(`Sprite: "Raycaster.camera" needs to be set in order to raycast against sprites.`),Xc.setFromMatrixScale(this.matrixWorld),el.copy(e.camera.matrixWorld),this.modelViewMatrix.multiplyMatrices(e.camera.matrixWorldInverse,this.matrixWorld),Zc.setFromMatrixPosition(this.modelViewMatrix),e.camera.isPerspectiveCamera&&this.material.sizeAttenuation===!1&&Xc.multiplyScalar(-Zc.z);let n=this.material.rotation,r,i;n!==0&&(i=Math.cos(n),r=Math.sin(n));let a=this.center;cl(tl.set(-.5,-.5,0),Zc,a,Xc,r,i),cl(nl.set(.5,-.5,0),Zc,a,Xc,r,i),cl(rl.set(.5,.5,0),Zc,a,Xc,r,i),il.set(0,0),al.set(1,0),ol.set(1,1);let o=e.ray.intersectTriangle(tl,nl,rl,!1,Yc);if(o===null&&(cl(nl.set(-.5,.5,0),Zc,a,Xc,r,i),al.set(0,1),o=e.ray.intersectTriangle(tl,rl,nl,!1,Yc),o===null))return;let s=e.ray.origin.distanceTo(Yc);s<e.near||s>e.far||t.push({distance:s,point:Yc.clone(),uv:cc.getInterpolation(Yc,tl,nl,rl,il,al,ol,new V),face:null,object:this})}copy(e,t){return super.copy(e,t),e.center!==void 0&&this.center.copy(e.center),this.material=e.material,this}};function cl(e,t,n,r,i,a){Qc.subVectors(e,n).addScalar(.5).multiply(r),i===void 0?$c.copy(Qc):($c.x=a*Qc.x-i*Qc.y,$c.y=i*Qc.x+a*Qc.y),e.copy(t),e.x+=$c.x,e.y+=$c.y,e.applyMatrix4(el)}var ll=new H,ul=new H,dl=new H,fl=new H,pl=new H,ml=new H,hl=new H,gl=class{constructor(e=new H,t=new H(0,0,-1)){this.origin=e,this.direction=t}set(e,t){return this.origin.copy(e),this.direction.copy(t),this}copy(e){return this.origin.copy(e.origin),this.direction.copy(e.direction),this}at(e,t){return t.copy(this.origin).addScaledVector(this.direction,e)}lookAt(e){return this.direction.copy(e).sub(this.origin).normalize(),this}recast(e){return this.origin.copy(this.at(e,ll)),this}closestPointToPoint(e,t){t.subVectors(e,this.origin);let n=t.dot(this.direction);return n<0?t.copy(this.origin):t.copy(this.origin).addScaledVector(this.direction,n)}distanceToPoint(e){return Math.sqrt(this.distanceSqToPoint(e))}distanceSqToPoint(e){let t=ll.subVectors(e,this.origin).dot(this.direction);return t<0?this.origin.distanceToSquared(e):(ll.copy(this.origin).addScaledVector(this.direction,t),ll.distanceToSquared(e))}distanceSqToSegment(e,t,n,r){ul.copy(e).add(t).multiplyScalar(.5),dl.copy(t).sub(e).normalize(),fl.copy(this.origin).sub(ul);let i=e.distanceTo(t)*.5,a=-this.direction.dot(dl),o=fl.dot(this.direction),s=-fl.dot(dl),c=fl.lengthSq(),l=Math.abs(1-a*a),u,d,f,p;if(l>0)if(u=a*s-o,d=a*o-s,p=i*l,u>=0)if(d>=-p)if(d<=p){let e=1/l;u*=e,d*=e,f=u*(u+a*d+2*o)+d*(a*u+d+2*s)+c}else d=i,u=Math.max(0,-(a*d+o)),f=-u*u+d*(d+2*s)+c;else d=-i,u=Math.max(0,-(a*d+o)),f=-u*u+d*(d+2*s)+c;else d<=-p?(u=Math.max(0,-(-a*i+o)),d=u>0?-i:Math.min(Math.max(-i,-s),i),f=-u*u+d*(d+2*s)+c):d<=p?(u=0,d=Math.min(Math.max(-i,-s),i),f=d*(d+2*s)+c):(u=Math.max(0,-(a*i+o)),d=u>0?i:Math.min(Math.max(-i,-s),i),f=-u*u+d*(d+2*s)+c);else d=a>0?-i:i,u=Math.max(0,-(a*d+o)),f=-u*u+d*(d+2*s)+c;return n&&n.copy(this.origin).addScaledVector(this.direction,u),r&&r.copy(ul).addScaledVector(dl,d),f}intersectSphere(e,t){ll.subVectors(e.center,this.origin);let n=ll.dot(this.direction),r=ll.dot(ll)-n*n,i=e.radius*e.radius;if(r>i)return null;let a=Math.sqrt(i-r),o=n-a,s=n+a;return s<0?null:o<0?this.at(s,t):this.at(o,t)}intersectsSphere(e){return e.radius<0?!1:this.distanceSqToPoint(e.center)<=e.radius*e.radius}distanceToPlane(e){let t=e.normal.dot(this.direction);if(t===0)return e.distanceToPoint(this.origin)===0?0:null;let n=-(this.origin.dot(e.normal)+e.constant)/t;return n>=0?n:null}intersectPlane(e,t){let n=this.distanceToPlane(e);return n===null?null:this.at(n,t)}intersectsPlane(e){let t=e.distanceToPoint(this.origin);return t===0||e.normal.dot(this.direction)*t<0}intersectBox(e,t){let n,r,i,a,o,s,c=1/this.direction.x,l=1/this.direction.y,u=1/this.direction.z,d=this.origin;return c>=0?(n=(e.min.x-d.x)*c,r=(e.max.x-d.x)*c):(n=(e.max.x-d.x)*c,r=(e.min.x-d.x)*c),l>=0?(i=(e.min.y-d.y)*l,a=(e.max.y-d.y)*l):(i=(e.max.y-d.y)*l,a=(e.min.y-d.y)*l),n>a||i>r||((i>n||isNaN(n))&&(n=i),(a<r||isNaN(r))&&(r=a),u>=0?(o=(e.min.z-d.z)*u,s=(e.max.z-d.z)*u):(o=(e.max.z-d.z)*u,s=(e.min.z-d.z)*u),n>s||o>r)||((o>n||n!==n)&&(n=o),(s<r||r!==r)&&(r=s),r<0)?null:this.at(n>=0?n:r,t)}intersectsBox(e){return this.intersectBox(e,ll)!==null}intersectTriangle(e,t,n,r,i){pl.subVectors(t,e),ml.subVectors(n,e),hl.crossVectors(pl,ml);let a=this.direction.dot(hl),o;if(a>0){if(r)return null;o=1}else if(a<0)o=-1,a=-a;else return null;fl.subVectors(this.origin,e);let s=o*this.direction.dot(ml.crossVectors(fl,ml));if(s<0)return null;let c=o*this.direction.dot(pl.cross(fl));if(c<0||s+c>a)return null;let l=-o*fl.dot(hl);return l<0?null:this.at(l/a,i)}applyMatrix4(e){return this.origin.applyMatrix4(e),this.direction.transformDirection(e),this}equals(e){return e.origin.equals(this.origin)&&e.direction.equals(this.direction)}clone(){return new this.constructor().copy(this)}},_l=class extends Kc{constructor(e){super(),this.isMeshBasicMaterial=!0,this.type=`MeshBasicMaterial`,this.color=new W(16777215),this.map=null,this.lightMap=null,this.lightMapIntensity=1,this.aoMap=null,this.aoMapIntensity=1,this.specularMap=null,this.alphaMap=null,this.envMap=null,this.envMapRotation=new Ss,this.combine=0,this.reflectivity=1,this.refractionRatio=.98,this.wireframe=!1,this.wireframeLinewidth=1,this.wireframeLinecap=`round`,this.wireframeLinejoin=`round`,this.fog=!0,this.setValues(e)}copy(e){return super.copy(e),this.color.copy(e.color),this.map=e.map,this.lightMap=e.lightMap,this.lightMapIntensity=e.lightMapIntensity,this.aoMap=e.aoMap,this.aoMapIntensity=e.aoMapIntensity,this.specularMap=e.specularMap,this.alphaMap=e.alphaMap,this.envMap=e.envMap,this.envMapRotation.copy(e.envMapRotation),this.combine=e.combine,this.reflectivity=e.reflectivity,this.refractionRatio=e.refractionRatio,this.wireframe=e.wireframe,this.wireframeLinewidth=e.wireframeLinewidth,this.wireframeLinecap=e.wireframeLinecap,this.wireframeLinejoin=e.wireframeLinejoin,this.fog=e.fog,this}},vl=new fs,yl=new gl,bl=new Nc,xl=new H,Sl=new H,Cl=new H,wl=new H,Tl=new H,El=new H,Dl=new H,Ol=new H,kl=class extends zs{constructor(e=new Vc,t=new _l){super(),this.isMesh=!0,this.type=`Mesh`,this.geometry=e,this.material=t,this.morphTargetDictionary=void 0,this.morphTargetInfluences=void 0,this.count=1,this.updateMorphTargets()}copy(e,t){return super.copy(e,t),e.morphTargetInfluences!==void 0&&(this.morphTargetInfluences=e.morphTargetInfluences.slice()),e.morphTargetDictionary!==void 0&&(this.morphTargetDictionary=Object.assign({},e.morphTargetDictionary)),this.material=Array.isArray(e.material)?e.material.slice():e.material,this.geometry=e.geometry,this}updateMorphTargets(){let e=this.geometry.morphAttributes,t=Object.keys(e);if(t.length>0){let n=e[t[0]];if(n!==void 0){this.morphTargetInfluences=[],this.morphTargetDictionary={};for(let e=0,t=n.length;e<t;e++){let t=n[e].name||String(e);this.morphTargetInfluences.push(0),this.morphTargetDictionary[t]=e}}}}getVertexPosition(e,t){let n=this.geometry,r=n.attributes.position,i=n.morphAttributes.position,a=n.morphTargetsRelative;t.fromBufferAttribute(r,e);let o=this.morphTargetInfluences;if(i&&o){El.set(0,0,0);for(let n=0,r=i.length;n<r;n++){let r=o[n],s=i[n];r!==0&&(Tl.fromBufferAttribute(s,e),a?El.addScaledVector(Tl,r):El.addScaledVector(Tl.sub(t),r))}t.add(El)}return t}raycast(e,t){let n=this.geometry,r=this.material,i=this.matrixWorld;r!==void 0&&(n.boundingSphere===null&&n.computeBoundingSphere(),bl.copy(n.boundingSphere),bl.applyMatrix4(i),yl.copy(e.ray).recast(e.near),!(bl.containsPoint(yl.origin)===!1&&(yl.intersectSphere(bl,xl)===null||yl.origin.distanceToSquared(xl)>(e.far-e.near)**2))&&(vl.copy(i).invert(),yl.copy(e.ray).applyMatrix4(vl),!(n.boundingBox!==null&&yl.intersectsBox(n.boundingBox)===!1)&&this._computeIntersections(e,t,yl)))}_computeIntersections(e,t,n){let r,i=this.geometry,a=this.material,o=i.index,s=i.attributes.position,c=i.attributes.uv,l=i.attributes.uv1,u=i.attributes.normal,d=i.groups,f=i.drawRange;if(o!==null)if(Array.isArray(a))for(let i=0,s=d.length;i<s;i++){let s=d[i],p=a[s.materialIndex],m=Math.max(s.start,f.start),h=Math.min(o.count,Math.min(s.start+s.count,f.start+f.count));for(let i=m,a=h;i<a;i+=3){let a=o.getX(i),d=o.getX(i+1),f=o.getX(i+2);r=jl(this,p,e,n,c,l,u,a,d,f),r&&(r.faceIndex=Math.floor(i/3),r.face.materialIndex=s.materialIndex,t.push(r))}}else{let i=Math.max(0,f.start),s=Math.min(o.count,f.start+f.count);for(let d=i,f=s;d<f;d+=3){let i=o.getX(d),s=o.getX(d+1),f=o.getX(d+2);r=jl(this,a,e,n,c,l,u,i,s,f),r&&(r.faceIndex=Math.floor(d/3),t.push(r))}}else if(s!==void 0)if(Array.isArray(a))for(let i=0,o=d.length;i<o;i++){let o=d[i],p=a[o.materialIndex],m=Math.max(o.start,f.start),h=Math.min(s.count,Math.min(o.start+o.count,f.start+f.count));for(let i=m,a=h;i<a;i+=3){let a=i,s=i+1,d=i+2;r=jl(this,p,e,n,c,l,u,a,s,d),r&&(r.faceIndex=Math.floor(i/3),r.face.materialIndex=o.materialIndex,t.push(r))}}else{let i=Math.max(0,f.start),o=Math.min(s.count,f.start+f.count);for(let s=i,d=o;s<d;s+=3){let i=s,o=s+1,d=s+2;r=jl(this,a,e,n,c,l,u,i,o,d),r&&(r.faceIndex=Math.floor(s/3),t.push(r))}}}};function Al(e,t,n,r,i,a,o,s){let c;if(c=t.side===1?r.intersectTriangle(o,a,i,!0,s):r.intersectTriangle(i,a,o,t.side===0,s),c===null)return null;Ol.copy(s),Ol.applyMatrix4(e.matrixWorld);let l=n.ray.origin.distanceTo(Ol);return l<n.near||l>n.far?null:{distance:l,point:Ol.clone(),object:e}}function jl(e,t,n,r,i,a,o,s,c,l){e.getVertexPosition(s,Sl),e.getVertexPosition(c,Cl),e.getVertexPosition(l,wl);let u=Al(e,t,n,r,Sl,Cl,wl,Dl);if(u){let e=new H;cc.getBarycoord(Dl,Sl,Cl,wl,e),i&&(u.uv=cc.getInterpolatedAttribute(i,s,c,l,e,new V)),a&&(u.uv1=cc.getInterpolatedAttribute(a,s,c,l,e,new V)),o&&(u.normal=cc.getInterpolatedAttribute(o,s,c,l,e,new H),u.normal.dot(r.direction)>0&&u.normal.multiplyScalar(-1));let t={a:s,b:c,c:l,normal:new H,materialIndex:0};cc.getNormal(Sl,Cl,wl,t.normal),u.face=t,u.barycoord=e}return u}var Ml=class extends os{constructor(e=null,t=1,n=1,r,i,a,o,s,c=ji,l=ji,u,d){super(null,a,o,s,c,l,r,i,u,d),this.isDataTexture=!0,this.image={data:e,width:t,height:n},this.generateMipmaps=!1,this.flipY=!1,this.unpackAlignment=1}},Nl=class extends Dc{constructor(e,t,n,r=1){super(e,t,n),this.isInstancedBufferAttribute=!0,this.meshPerAttribute=r}copy(e){return super.copy(e),this.meshPerAttribute=e.meshPerAttribute,this}toJSON(){let e=super.toJSON();return e.meshPerAttribute=this.meshPerAttribute,e.isInstancedBufferAttribute=!0,e}},Pl=new fs,Fl=new fs,Il=[],Ll=new lc,Rl=new fs,zl=new kl,Bl=new Nc,Vl=class extends kl{constructor(e,t,n){super(e,t),this.isInstancedMesh=!0,this.instanceMatrix=new Nl(new Float32Array(n*16),16),this.previousInstanceMatrix=null,this.instanceColor=null,this.morphTexture=null,this.count=n,this.boundingBox=null,this.boundingSphere=null;for(let e=0;e<n;e++)this.setMatrixAt(e,Rl)}computeBoundingBox(){let e=this.geometry,t=this.count;this.boundingBox===null&&(this.boundingBox=new lc),e.boundingBox===null&&e.computeBoundingBox(),this.boundingBox.makeEmpty();for(let n=0;n<t;n++)this.getMatrixAt(n,Pl),Ll.copy(e.boundingBox).applyMatrix4(Pl),this.boundingBox.union(Ll)}computeBoundingSphere(){let e=this.geometry,t=this.count;this.boundingSphere===null&&(this.boundingSphere=new Nc),e.boundingSphere===null&&e.computeBoundingSphere(),this.boundingSphere.makeEmpty();for(let n=0;n<t;n++)this.getMatrixAt(n,Pl),Bl.copy(e.boundingSphere).applyMatrix4(Pl),this.boundingSphere.union(Bl)}copy(e,t){return super.copy(e,t),this.instanceMatrix.copy(e.instanceMatrix),e.previousInstanceMatrix!==null&&(this.previousInstanceMatrix=e.previousInstanceMatrix.clone()),e.morphTexture!==null&&(this.morphTexture=e.morphTexture.clone()),e.instanceColor!==null&&(this.instanceColor=e.instanceColor.clone()),this.count=e.count,e.boundingBox!==null&&(this.boundingBox=e.boundingBox.clone()),e.boundingSphere!==null&&(this.boundingSphere=e.boundingSphere.clone()),this}getColorAt(e,t){return this.instanceColor===null?t.setRGB(1,1,1):t.fromArray(this.instanceColor.array,e*3)}getMatrixAt(e,t){return t.fromArray(this.instanceMatrix.array,e*16)}getMorphAt(e,t){let n=t.morphTargetInfluences,r=this.morphTexture.source.data.data,i=e*(n.length+1)+1;for(let e=0;e<n.length;e++)n[e]=r[i+e]}raycast(e,t){let n=this.matrixWorld,r=this.count;if(zl.geometry=this.geometry,zl.material=this.material,zl.material!==void 0&&(this.boundingSphere===null&&this.computeBoundingSphere(),Bl.copy(this.boundingSphere),Bl.applyMatrix4(n),e.ray.intersectsSphere(Bl)!==!1))for(let i=0;i<r;i++){this.getMatrixAt(i,Pl),Fl.multiplyMatrices(n,Pl),zl.matrixWorld=Fl,zl.raycast(e,Il);for(let e=0,n=Il.length;e<n;e++){let n=Il[e];n.instanceId=i,n.object=this,t.push(n)}Il.length=0}}setColorAt(e,t){return this.instanceColor===null&&(this.instanceColor=new Nl(new Float32Array(this.instanceMatrix.count*3).fill(1),3)),t.toArray(this.instanceColor.array,e*3),this}setMatrixAt(e,t){return t.toArray(this.instanceMatrix.array,e*16),this}setMorphAt(e,t){let n=t.morphTargetInfluences,r=n.length+1;this.morphTexture===null&&(this.morphTexture=new Ml(new Float32Array(r*this.count),r,this.count,ta,Ui));let i=this.morphTexture.source.data.data,a=0;for(let e=0;e<n.length;e++)a+=n[e];let o=this.geometry.morphTargetsRelative?1:1-a,s=r*e;return i[s]=o,i.set(n,s+1),this}updateMorphTargets(){}dispose(){this.dispatchEvent({type:`dispose`}),this.morphTexture!==null&&(this.morphTexture.dispose(),this.morphTexture=null)}},Hl=new H,Ul=new H,Wl=new U,Gl=class{constructor(e=new H(1,0,0),t=0){this.isPlane=!0,this.normal=e,this.constant=t}set(e,t){return this.normal.copy(e),this.constant=t,this}setComponents(e,t,n,r){return this.normal.set(e,t,n),this.constant=r,this}setFromNormalAndCoplanarPoint(e,t){return this.normal.copy(e),this.constant=-t.dot(this.normal),this}setFromCoplanarPoints(e,t,n){let r=Hl.subVectors(n,t).cross(Ul.subVectors(e,t)).normalize();return this.setFromNormalAndCoplanarPoint(r,e),this}copy(e){return this.normal.copy(e.normal),this.constant=e.constant,this}normalize(){let e=1/this.normal.length();return this.normal.multiplyScalar(e),this.constant*=e,this}negate(){return this.constant*=-1,this.normal.negate(),this}distanceToPoint(e){return this.normal.dot(e)+this.constant}distanceToSphere(e){return this.distanceToPoint(e.center)-e.radius}projectPoint(e,t){return t.copy(e).addScaledVector(this.normal,-this.distanceToPoint(e))}intersectLine(e,t,n=!0){let r=e.delta(Hl),i=this.normal.dot(r);if(i===0)return this.distanceToPoint(e.start)===0?t.copy(e.start):null;let a=-(e.start.dot(this.normal)+this.constant)/i;return n===!0&&(a<0||a>1)?null:t.copy(e.start).addScaledVector(r,a)}intersectsLine(e){let t=this.distanceToPoint(e.start),n=this.distanceToPoint(e.end);return t<0&&n>0||n<0&&t>0}intersectsBox(e){return e.intersectsPlane(this)}intersectsSphere(e){return e.intersectsPlane(this)}coplanarPoint(e){return e.copy(this.normal).multiplyScalar(-this.constant)}applyMatrix4(e,t){let n=t||Wl.getNormalMatrix(e),r=this.coplanarPoint(Hl).applyMatrix4(e),i=this.normal.applyMatrix3(n).normalize();return this.constant=-r.dot(i),this}translate(e){return this.constant-=e.dot(this.normal),this}equals(e){return e.normal.equals(this.normal)&&e.constant===this.constant}clone(){return new this.constructor().copy(this)}},Kl=new Nc,ql=new V(.5,.5),Jl=new H,Yl=class{constructor(e=new Gl,t=new Gl,n=new Gl,r=new Gl,i=new Gl,a=new Gl){this.planes=[e,t,n,r,i,a]}set(e,t,n,r,i,a){let o=this.planes;return o[0].copy(e),o[1].copy(t),o[2].copy(n),o[3].copy(r),o[4].copy(i),o[5].copy(a),this}copy(e){let t=this.planes;for(let n=0;n<6;n++)t[n].copy(e.planes[n]);return this}setFromProjectionMatrix(e,t=ro,n=!1){let r=this.planes,i=e.elements,a=i[0],o=i[1],s=i[2],c=i[3],l=i[4],u=i[5],d=i[6],f=i[7],p=i[8],m=i[9],h=i[10],g=i[11],_=i[12],v=i[13],y=i[14],b=i[15];if(r[0].setComponents(c-a,f-l,g-p,b-_).normalize(),r[1].setComponents(c+a,f+l,g+p,b+_).normalize(),r[2].setComponents(c+o,f+u,g+m,b+v).normalize(),r[3].setComponents(c-o,f-u,g-m,b-v).normalize(),n)r[4].setComponents(s,d,h,y).normalize(),r[5].setComponents(c-s,f-d,g-h,b-y).normalize();else if(r[4].setComponents(c-s,f-d,g-h,b-y).normalize(),t===2e3)r[5].setComponents(c+s,f+d,g+h,b+y).normalize();else if(t===2001)r[5].setComponents(s,d,h,y).normalize();else throw Error(`THREE.Frustum.setFromProjectionMatrix(): Invalid coordinate system: `+t);return this}intersectsObject(e){if(e.boundingSphere!==void 0)e.boundingSphere===null&&e.computeBoundingSphere(),Kl.copy(e.boundingSphere).applyMatrix4(e.matrixWorld);else{let t=e.geometry;t.boundingSphere===null&&t.computeBoundingSphere(),Kl.copy(t.boundingSphere).applyMatrix4(e.matrixWorld)}return this.intersectsSphere(Kl)}intersectsSprite(e){return Kl.center.set(0,0,0),Kl.radius=.7071067811865476+ql.distanceTo(e.center),Kl.applyMatrix4(e.matrixWorld),this.intersectsSphere(Kl)}intersectsSphere(e){let t=this.planes,n=e.center,r=-e.radius;for(let e=0;e<6;e++)if(t[e].distanceToPoint(n)<r)return!1;return!0}intersectsBox(e){let t=this.planes;for(let n=0;n<6;n++){let r=t[n];if(Jl.x=r.normal.x>0?e.max.x:e.min.x,Jl.y=r.normal.y>0?e.max.y:e.min.y,Jl.z=r.normal.z>0?e.max.z:e.min.z,r.distanceToPoint(Jl)<0)return!1}return!0}containsPoint(e){let t=this.planes;for(let n=0;n<6;n++)if(t[n].distanceToPoint(e)<0)return!1;return!0}clone(){return new this.constructor().copy(this)}},Xl=class extends Kc{constructor(e){super(),this.isLineBasicMaterial=!0,this.type=`LineBasicMaterial`,this.color=new W(16777215),this.map=null,this.linewidth=1,this.linecap=`round`,this.linejoin=`round`,this.fog=!0,this.setValues(e)}copy(e){return super.copy(e),this.color.copy(e.color),this.map=e.map,this.linewidth=e.linewidth,this.linecap=e.linecap,this.linejoin=e.linejoin,this.fog=e.fog,this}},Zl=new H,Ql=new H,$l=new fs,eu=new gl,tu=new Nc,nu=new H,ru=new H,iu=class extends zs{constructor(e=new Vc,t=new Xl){super(),this.isLine=!0,this.type=`Line`,this.geometry=e,this.material=t,this.morphTargetDictionary=void 0,this.morphTargetInfluences=void 0,this.updateMorphTargets()}copy(e,t){return super.copy(e,t),this.material=Array.isArray(e.material)?e.material.slice():e.material,this.geometry=e.geometry,this}computeLineDistances(){let e=this.geometry;if(e.index===null){let t=e.attributes.position,n=[0];for(let e=1,r=t.count;e<r;e++)Zl.fromBufferAttribute(t,e-1),Ql.fromBufferAttribute(t,e),n[e]=n[e-1],n[e]+=Zl.distanceTo(Ql);e.setAttribute(`lineDistance`,new G(n,1))}else R(`Line.computeLineDistances(): Computation only possible with non-indexed BufferGeometry.`);return this}raycast(e,t){let n=this.geometry,r=this.matrixWorld,i=e.params.Line.threshold,a=n.drawRange;if(n.boundingSphere===null&&n.computeBoundingSphere(),tu.copy(n.boundingSphere),tu.applyMatrix4(r),tu.radius+=i,e.ray.intersectsSphere(tu)===!1)return;$l.copy(r).invert(),eu.copy(e.ray).applyMatrix4($l);let o=i/((this.scale.x+this.scale.y+this.scale.z)/3),s=o*o,c=this.isLineSegments?2:1,l=n.index,u=n.attributes.position;if(l!==null){let n=Math.max(0,a.start),r=Math.min(l.count,a.start+a.count);for(let i=n,a=r-1;i<a;i+=c){let n=l.getX(i),r=l.getX(i+1),a=au(this,e,eu,s,n,r,i);a&&t.push(a)}if(this.isLineLoop){let i=l.getX(r-1),a=l.getX(n),o=au(this,e,eu,s,i,a,r-1);o&&t.push(o)}}else{let n=Math.max(0,a.start),r=Math.min(u.count,a.start+a.count);for(let i=n,a=r-1;i<a;i+=c){let n=au(this,e,eu,s,i,i+1,i);n&&t.push(n)}if(this.isLineLoop){let i=au(this,e,eu,s,r-1,n,r-1);i&&t.push(i)}}}updateMorphTargets(){let e=this.geometry.morphAttributes,t=Object.keys(e);if(t.length>0){let n=e[t[0]];if(n!==void 0){this.morphTargetInfluences=[],this.morphTargetDictionary={};for(let e=0,t=n.length;e<t;e++){let t=n[e].name||String(e);this.morphTargetInfluences.push(0),this.morphTargetDictionary[t]=e}}}}};function au(e,t,n,r,i,a,o){let s=e.geometry.attributes.position;if(Zl.fromBufferAttribute(s,i),Ql.fromBufferAttribute(s,a),n.distanceSqToSegment(Zl,Ql,nu,ru)>r)return;nu.applyMatrix4(e.matrixWorld);let c=t.ray.origin.distanceTo(nu);if(!(c<t.near||c>t.far))return{distance:c,point:ru.clone().applyMatrix4(e.matrixWorld),index:o,face:null,faceIndex:null,barycoord:null,object:e}}var ou=new H,su=new H,cu=class extends iu{constructor(e,t){super(e,t),this.isLineSegments=!0,this.type=`LineSegments`}computeLineDistances(){let e=this.geometry;if(e.index===null){let t=e.attributes.position,n=[];for(let e=0,r=t.count;e<r;e+=2)ou.fromBufferAttribute(t,e),su.fromBufferAttribute(t,e+1),n[e]=e===0?0:n[e-1],n[e+1]=n[e]+ou.distanceTo(su);e.setAttribute(`lineDistance`,new G(n,1))}else R(`LineSegments.computeLineDistances(): Computation only possible with non-indexed BufferGeometry.`);return this}},lu=class extends os{constructor(e=[],t=301,n,r,i,a,o,s,c,l){super(e,t,n,r,i,a,o,s,c,l),this.isCubeTexture=!0,this.flipY=!1}get images(){return this.image}set images(e){this.image=e}},uu=class extends os{constructor(e,t,n,r,i,a,o,s,c){super(e,t,n,r,i,a,o,s,c),this.isCanvasTexture=!0,this.needsUpdate=!0}},du=class extends os{constructor(e,t,n=Hi,r,i,a,o=ji,s=ji,c,l=$i,u=1){if(l!==1026&&l!==1027)throw Error(`DepthTexture format must be either THREE.DepthFormat or THREE.DepthStencilFormat`);super({width:e,height:t,depth:u},r,i,a,o,s,l,n,c),this.isDepthTexture=!0,this.flipY=!1,this.generateMipmaps=!1,this.compareFunction=null}copy(e){return super.copy(e),this.source=new ns(Object.assign({},e.image)),this.compareFunction=e.compareFunction,this}toJSON(e){let t=super.toJSON(e);return this.compareFunction!==null&&(t.compareFunction=this.compareFunction),t}},fu=class extends du{constructor(e,t=Hi,n=301,r,i,a=ji,o=ji,s,c=$i){let l={width:e,height:e,depth:1},u=[l,l,l,l,l,l];super(e,e,t,n,r,i,a,o,s,c),this.image=u,this.isCubeDepthTexture=!0,this.isCubeTexture=!0}get images(){return this.image}set images(e){this.image=e}},pu=class extends os{constructor(e=null){super(),this.sourceTexture=e,this.isExternalTexture=!0}copy(e){return super.copy(e),this.sourceTexture=e.sourceTexture,this}},mu=class e extends Vc{constructor(e=1,t=1,n=1,r=1,i=1,a=1){super(),this.type=`BoxGeometry`,this.parameters={width:e,height:t,depth:n,widthSegments:r,heightSegments:i,depthSegments:a};let o=this;r=Math.floor(r),i=Math.floor(i),a=Math.floor(a);let s=[],c=[],l=[],u=[],d=0,f=0;p(`z`,`y`,`x`,-1,-1,n,t,e,a,i,0),p(`z`,`y`,`x`,1,-1,n,t,-e,a,i,1),p(`x`,`z`,`y`,1,1,e,n,t,r,a,2),p(`x`,`z`,`y`,1,-1,e,n,-t,r,a,3),p(`x`,`y`,`z`,1,-1,e,t,n,r,i,4),p(`x`,`y`,`z`,-1,-1,e,t,-n,r,i,5),this.setIndex(s),this.setAttribute(`position`,new G(c,3)),this.setAttribute(`normal`,new G(l,3)),this.setAttribute(`uv`,new G(u,2));function p(e,t,n,r,i,a,p,m,h,g,_){let v=a/h,y=p/g,b=a/2,x=p/2,S=m/2,C=h+1,w=g+1,T=0,E=0,D=new H;for(let a=0;a<w;a++){let o=a*y-x;for(let s=0;s<C;s++)D[e]=(s*v-b)*r,D[t]=o*i,D[n]=S,c.push(D.x,D.y,D.z),D[e]=0,D[t]=0,D[n]=m>0?1:-1,l.push(D.x,D.y,D.z),u.push(s/h),u.push(1-a/g),T+=1}for(let e=0;e<g;e++)for(let t=0;t<h;t++){let n=d+t+C*e,r=d+t+C*(e+1),i=d+(t+1)+C*(e+1),a=d+(t+1)+C*e;s.push(n,r,a),s.push(r,i,a),E+=6}o.addGroup(f,E,_),f+=E,d+=T}}copy(e){return super.copy(e),this.parameters=Object.assign({},e.parameters),this}static fromJSON(t){return new e(t.width,t.height,t.depth,t.widthSegments,t.heightSegments,t.depthSegments)}},hu=class e extends Vc{constructor(e=1,t=1,n=1,r=32,i=1,a=!1,o=0,s=Math.PI*2){super(),this.type=`CylinderGeometry`,this.parameters={radiusTop:e,radiusBottom:t,height:n,radialSegments:r,heightSegments:i,openEnded:a,thetaStart:o,thetaLength:s};let c=this;r=Math.floor(r),i=Math.floor(i);let l=[],u=[],d=[],f=[],p=0,m=[],h=n/2,g=0;_(),a===!1&&(e>0&&v(!0),t>0&&v(!1)),this.setIndex(l),this.setAttribute(`position`,new G(u,3)),this.setAttribute(`normal`,new G(d,3)),this.setAttribute(`uv`,new G(f,2));function _(){let a=new H,_=new H,v=0,y=(t-e)/n;for(let c=0;c<=i;c++){let l=[],g=c/i,v=g*(t-e)+e;for(let e=0;e<=r;e++){let t=e/r,i=t*s+o,c=Math.sin(i),m=Math.cos(i);_.x=v*c,_.y=-g*n+h,_.z=v*m,u.push(_.x,_.y,_.z),a.set(c,y,m).normalize(),d.push(a.x,a.y,a.z),f.push(t,1-g),l.push(p++)}m.push(l)}for(let n=0;n<r;n++)for(let r=0;r<i;r++){let a=m[r][n],o=m[r+1][n],s=m[r+1][n+1],c=m[r][n+1];(e>0||r!==0)&&(l.push(a,o,c),v+=3),(t>0||r!==i-1)&&(l.push(o,s,c),v+=3)}c.addGroup(g,v,0),g+=v}function v(n){let i=p,a=new V,m=new H,_=0,v=n===!0?e:t,y=n===!0?1:-1;for(let e=1;e<=r;e++)u.push(0,h*y,0),d.push(0,y,0),f.push(.5,.5),p++;let b=p;for(let e=0;e<=r;e++){let t=e/r*s+o,n=Math.cos(t),i=Math.sin(t);m.x=v*i,m.y=h*y,m.z=v*n,u.push(m.x,m.y,m.z),d.push(0,y,0),a.x=n*.5+.5,a.y=i*.5*y+.5,f.push(a.x,a.y),p++}for(let e=0;e<r;e++){let t=i+e,r=b+e;n===!0?l.push(r,r+1,t):l.push(r+1,r,t),_+=3}c.addGroup(g,_,n===!0?1:2),g+=_}}copy(e){return super.copy(e),this.parameters=Object.assign({},e.parameters),this}static fromJSON(t){return new e(t.radiusTop,t.radiusBottom,t.height,t.radialSegments,t.heightSegments,t.openEnded,t.thetaStart,t.thetaLength)}},gu=class e extends hu{constructor(e=1,t=1,n=32,r=1,i=!1,a=0,o=Math.PI*2){super(0,e,t,n,r,i,a,o),this.type=`ConeGeometry`,this.parameters={radius:e,height:t,radialSegments:n,heightSegments:r,openEnded:i,thetaStart:a,thetaLength:o}}static fromJSON(t){return new e(t.radius,t.height,t.radialSegments,t.heightSegments,t.openEnded,t.thetaStart,t.thetaLength)}},_u=new H,vu=new H,yu=new H,bu=new cc,xu=class extends Vc{constructor(e=null,t=1){if(super(),this.type=`EdgesGeometry`,this.parameters={geometry:e,thresholdAngle:t},e!==null){let n=10**4,r=Math.cos(yo*t),i=e.getIndex(),a=e.getAttribute(`position`),o=i?i.count:a.count,s=[0,0,0],c=[`a`,`b`,`c`],l=[,,,],u={},d=[];for(let e=0;e<o;e+=3){i?(s[0]=i.getX(e),s[1]=i.getX(e+1),s[2]=i.getX(e+2)):(s[0]=e,s[1]=e+1,s[2]=e+2);let{a:t,b:o,c:f}=bu;if(t.fromBufferAttribute(a,s[0]),o.fromBufferAttribute(a,s[1]),f.fromBufferAttribute(a,s[2]),bu.getNormal(yu),l[0]=`${Math.round(t.x*n)},${Math.round(t.y*n)},${Math.round(t.z*n)}`,l[1]=`${Math.round(o.x*n)},${Math.round(o.y*n)},${Math.round(o.z*n)}`,l[2]=`${Math.round(f.x*n)},${Math.round(f.y*n)},${Math.round(f.z*n)}`,!(l[0]===l[1]||l[1]===l[2]||l[2]===l[0]))for(let e=0;e<3;e++){let t=(e+1)%3,n=l[e],i=l[t],a=bu[c[e]],o=bu[c[t]],f=`${n}_${i}`,p=`${i}_${n}`;p in u&&u[p]?(yu.dot(u[p].normal)<=r&&(d.push(a.x,a.y,a.z),d.push(o.x,o.y,o.z)),u[p]=null):f in u||(u[f]={index0:s[e],index1:s[t],normal:yu.clone()})}}for(let e in u)if(u[e]){let{index0:t,index1:n}=u[e];_u.fromBufferAttribute(a,t),vu.fromBufferAttribute(a,n),d.push(_u.x,_u.y,_u.z),d.push(vu.x,vu.y,vu.z)}this.setAttribute(`position`,new G(d,3))}}copy(e){return super.copy(e),this.parameters=Object.assign({},e.parameters),this}},Su=class{constructor(){this.type=`Curve`,this.arcLengthDivisions=200,this.needsUpdate=!1,this.cacheArcLengths=null}getPoint(){R(`Curve: .getPoint() not implemented.`)}getPointAt(e,t){let n=this.getUtoTmapping(e);return this.getPoint(n,t)}getPoints(e=5){let t=[];for(let n=0;n<=e;n++)t.push(this.getPoint(n/e));return t}getSpacedPoints(e=5){let t=[];for(let n=0;n<=e;n++)t.push(this.getPointAt(n/e));return t}getLength(){let e=this.getLengths();return e[e.length-1]}getLengths(e=this.arcLengthDivisions){if(this.cacheArcLengths&&this.cacheArcLengths.length===e+1&&!this.needsUpdate)return this.cacheArcLengths;this.needsUpdate=!1;let t=[],n,r=this.getPoint(0),i=0;t.push(0);for(let a=1;a<=e;a++)n=this.getPoint(a/e),i+=n.distanceTo(r),t.push(i),r=n;return this.cacheArcLengths=t,t}updateArcLengths(){this.needsUpdate=!0,this.getLengths()}getUtoTmapping(e,t=null){let n=this.getLengths(),r=0,i=n.length,a;a=t||e*n[i-1];let o=0,s=i-1,c;for(;o<=s;)if(r=Math.floor(o+(s-o)/2),c=n[r]-a,c<0)o=r+1;else if(c>0)s=r-1;else{s=r;break}if(r=s,n[r]===a)return r/(i-1);let l=n[r],u=n[r+1]-l,d=(a-l)/u;return(r+d)/(i-1)}getTangent(e,t){let n=1e-4,r=e-n,i=e+n;r<0&&(r=0),i>1&&(i=1);let a=this.getPoint(r),o=this.getPoint(i),s=t||(a.isVector2?new V:new H);return s.copy(o).sub(a).normalize(),s}getTangentAt(e,t){let n=this.getUtoTmapping(e);return this.getTangent(n,t)}computeFrenetFrames(e,t=!1){let n=new H,r=[],i=[],a=[],o=new H,s=new fs;for(let t=0;t<=e;t++){let n=t/e;r[t]=this.getTangentAt(n,new H)}i[0]=new H,a[0]=new H;let c=Number.MAX_VALUE,l=Math.abs(r[0].x),u=Math.abs(r[0].y),d=Math.abs(r[0].z);l<=c&&(c=l,n.set(1,0,0)),u<=c&&(c=u,n.set(0,1,0)),d<=c&&n.set(0,0,1),o.crossVectors(r[0],n).normalize(),i[0].crossVectors(r[0],o),a[0].crossVectors(r[0],i[0]);for(let t=1;t<=e;t++){if(i[t]=i[t-1].clone(),a[t]=a[t-1].clone(),o.crossVectors(r[t-1],r[t]),o.length()>2**-52){o.normalize();let e=Math.acos(B(r[t-1].dot(r[t]),-1,1));i[t].applyMatrix4(s.makeRotationAxis(o,e))}a[t].crossVectors(r[t],i[t])}if(t===!0){let t=Math.acos(B(i[0].dot(i[e]),-1,1));t/=e,r[0].dot(o.crossVectors(i[0],i[e]))>0&&(t=-t);for(let n=1;n<=e;n++)i[n].applyMatrix4(s.makeRotationAxis(r[n],t*n)),a[n].crossVectors(r[n],i[n])}return{tangents:r,normals:i,binormals:a}}clone(){return new this.constructor().copy(this)}copy(e){return this.arcLengthDivisions=e.arcLengthDivisions,this}toJSON(){let e={metadata:{version:4.7,type:`Curve`,generator:`Curve.toJSON`}};return e.arcLengthDivisions=this.arcLengthDivisions,e.type=this.type,e}fromJSON(e){return this.arcLengthDivisions=e.arcLengthDivisions,this}},Cu=class extends Su{constructor(e=0,t=0,n=1,r=1,i=0,a=Math.PI*2,o=!1,s=0){super(),this.isEllipseCurve=!0,this.type=`EllipseCurve`,this.aX=e,this.aY=t,this.xRadius=n,this.yRadius=r,this.aStartAngle=i,this.aEndAngle=a,this.aClockwise=o,this.aRotation=s}getPoint(e,t=new V){let n=t,r=Math.PI*2,i=this.aEndAngle-this.aStartAngle,a=Math.abs(i)<2**-52;for(;i<0;)i+=r;for(;i>r;)i-=r;i<2**-52&&(i=a?0:r),this.aClockwise===!0&&!a&&(i===r?i=-r:i-=r);let o=this.aStartAngle+e*i,s=this.aX+this.xRadius*Math.cos(o),c=this.aY+this.yRadius*Math.sin(o);if(this.aRotation!==0){let e=Math.cos(this.aRotation),t=Math.sin(this.aRotation),n=s-this.aX,r=c-this.aY;s=n*e-r*t+this.aX,c=n*t+r*e+this.aY}return n.set(s,c)}copy(e){return super.copy(e),this.aX=e.aX,this.aY=e.aY,this.xRadius=e.xRadius,this.yRadius=e.yRadius,this.aStartAngle=e.aStartAngle,this.aEndAngle=e.aEndAngle,this.aClockwise=e.aClockwise,this.aRotation=e.aRotation,this}toJSON(){let e=super.toJSON();return e.aX=this.aX,e.aY=this.aY,e.xRadius=this.xRadius,e.yRadius=this.yRadius,e.aStartAngle=this.aStartAngle,e.aEndAngle=this.aEndAngle,e.aClockwise=this.aClockwise,e.aRotation=this.aRotation,e}fromJSON(e){return super.fromJSON(e),this.aX=e.aX,this.aY=e.aY,this.xRadius=e.xRadius,this.yRadius=e.yRadius,this.aStartAngle=e.aStartAngle,this.aEndAngle=e.aEndAngle,this.aClockwise=e.aClockwise,this.aRotation=e.aRotation,this}},wu=class extends Cu{constructor(e,t,n,r,i,a){super(e,t,n,n,r,i,a),this.isArcCurve=!0,this.type=`ArcCurve`}};function Tu(){let e=0,t=0,n=0,r=0;function i(i,a,o,s){e=i,t=o,n=-3*i+3*a-2*o-s,r=2*i-2*a+o+s}return{initCatmullRom:function(e,t,n,r,a){i(t,n,a*(n-e),a*(r-t))},initNonuniformCatmullRom:function(e,t,n,r,a,o,s){let c=(t-e)/a-(n-e)/(a+o)+(n-t)/o,l=(n-t)/o-(r-t)/(o+s)+(r-n)/s;c*=o,l*=o,i(t,n,c,l)},calc:function(i){let a=i*i,o=a*i;return e+t*i+n*a+r*o}}}var Eu=new H,Du=new H,Ou=new Tu,ku=new Tu,Au=new Tu,ju=class extends Su{constructor(e=[],t=!1,n=`centripetal`,r=.5){super(),this.isCatmullRomCurve3=!0,this.type=`CatmullRomCurve3`,this.points=e,this.closed=t,this.curveType=n,this.tension=r}getPoint(e,t=new H){let n=t,r=this.points,i=r.length,a=(i-+!this.closed)*e,o=Math.floor(a),s=a-o;this.closed?o+=o>0?0:(Math.floor(Math.abs(o)/i)+1)*i:s===0&&o===i-1&&(o=i-2,s=1);let c,l;this.closed||o>0?c=r[(o-1)%i]:(Du.subVectors(r[0],r[1]).add(r[0]),c=Du);let u=r[o%i],d=r[(o+1)%i];if(this.closed||o+2<i?l=r[(o+2)%i]:(Eu.subVectors(r[i-1],r[i-2]).add(r[i-1]),l=Eu),this.curveType===`centripetal`||this.curveType===`chordal`){let e=this.curveType===`chordal`?.5:.25,t=c.distanceToSquared(u)**+e,n=u.distanceToSquared(d)**+e,r=d.distanceToSquared(l)**+e;n<1e-4&&(n=1),t<1e-4&&(t=n),r<1e-4&&(r=n),Ou.initNonuniformCatmullRom(c.x,u.x,d.x,l.x,t,n,r),ku.initNonuniformCatmullRom(c.y,u.y,d.y,l.y,t,n,r),Au.initNonuniformCatmullRom(c.z,u.z,d.z,l.z,t,n,r)}else this.curveType===`catmullrom`&&(Ou.initCatmullRom(c.x,u.x,d.x,l.x,this.tension),ku.initCatmullRom(c.y,u.y,d.y,l.y,this.tension),Au.initCatmullRom(c.z,u.z,d.z,l.z,this.tension));return n.set(Ou.calc(s),ku.calc(s),Au.calc(s)),n}copy(e){super.copy(e),this.points=[];for(let t=0,n=e.points.length;t<n;t++){let n=e.points[t];this.points.push(n.clone())}return this.closed=e.closed,this.curveType=e.curveType,this.tension=e.tension,this}toJSON(){let e=super.toJSON();e.points=[];for(let t=0,n=this.points.length;t<n;t++){let n=this.points[t];e.points.push(n.toArray())}return e.closed=this.closed,e.curveType=this.curveType,e.tension=this.tension,e}fromJSON(e){super.fromJSON(e),this.points=[];for(let t=0,n=e.points.length;t<n;t++){let n=e.points[t];this.points.push(new H().fromArray(n))}return this.closed=e.closed,this.curveType=e.curveType,this.tension=e.tension,this}};function Mu(e,t,n,r,i){let a=(r-t)*.5,o=(i-n)*.5,s=e*e,c=e*s;return(2*n-2*r+a+o)*c+(-3*n+3*r-2*a-o)*s+a*e+n}function Nu(e,t){let n=1-e;return n*n*t}function Pu(e,t){return 2*(1-e)*e*t}function Fu(e,t){return e*e*t}function Iu(e,t,n,r){return Nu(e,t)+Pu(e,n)+Fu(e,r)}function Lu(e,t){let n=1-e;return n*n*n*t}function Ru(e,t){let n=1-e;return 3*n*n*e*t}function zu(e,t){return 3*(1-e)*e*e*t}function Bu(e,t){return e*e*e*t}function Vu(e,t,n,r,i){return Lu(e,t)+Ru(e,n)+zu(e,r)+Bu(e,i)}var Hu=class extends Su{constructor(e=new V,t=new V,n=new V,r=new V){super(),this.isCubicBezierCurve=!0,this.type=`CubicBezierCurve`,this.v0=e,this.v1=t,this.v2=n,this.v3=r}getPoint(e,t=new V){let n=t,r=this.v0,i=this.v1,a=this.v2,o=this.v3;return n.set(Vu(e,r.x,i.x,a.x,o.x),Vu(e,r.y,i.y,a.y,o.y)),n}copy(e){return super.copy(e),this.v0.copy(e.v0),this.v1.copy(e.v1),this.v2.copy(e.v2),this.v3.copy(e.v3),this}toJSON(){let e=super.toJSON();return e.v0=this.v0.toArray(),e.v1=this.v1.toArray(),e.v2=this.v2.toArray(),e.v3=this.v3.toArray(),e}fromJSON(e){return super.fromJSON(e),this.v0.fromArray(e.v0),this.v1.fromArray(e.v1),this.v2.fromArray(e.v2),this.v3.fromArray(e.v3),this}},Uu=class extends Su{constructor(e=new H,t=new H,n=new H,r=new H){super(),this.isCubicBezierCurve3=!0,this.type=`CubicBezierCurve3`,this.v0=e,this.v1=t,this.v2=n,this.v3=r}getPoint(e,t=new H){let n=t,r=this.v0,i=this.v1,a=this.v2,o=this.v3;return n.set(Vu(e,r.x,i.x,a.x,o.x),Vu(e,r.y,i.y,a.y,o.y),Vu(e,r.z,i.z,a.z,o.z)),n}copy(e){return super.copy(e),this.v0.copy(e.v0),this.v1.copy(e.v1),this.v2.copy(e.v2),this.v3.copy(e.v3),this}toJSON(){let e=super.toJSON();return e.v0=this.v0.toArray(),e.v1=this.v1.toArray(),e.v2=this.v2.toArray(),e.v3=this.v3.toArray(),e}fromJSON(e){return super.fromJSON(e),this.v0.fromArray(e.v0),this.v1.fromArray(e.v1),this.v2.fromArray(e.v2),this.v3.fromArray(e.v3),this}},Wu=class extends Su{constructor(e=new V,t=new V){super(),this.isLineCurve=!0,this.type=`LineCurve`,this.v1=e,this.v2=t}getPoint(e,t=new V){let n=t;return e===1?n.copy(this.v2):(n.copy(this.v2).sub(this.v1),n.multiplyScalar(e).add(this.v1)),n}getPointAt(e,t){return this.getPoint(e,t)}getTangent(e,t=new V){return t.subVectors(this.v2,this.v1).normalize()}getTangentAt(e,t){return this.getTangent(e,t)}copy(e){return super.copy(e),this.v1.copy(e.v1),this.v2.copy(e.v2),this}toJSON(){let e=super.toJSON();return e.v1=this.v1.toArray(),e.v2=this.v2.toArray(),e}fromJSON(e){return super.fromJSON(e),this.v1.fromArray(e.v1),this.v2.fromArray(e.v2),this}},Gu=class extends Su{constructor(e=new H,t=new H){super(),this.isLineCurve3=!0,this.type=`LineCurve3`,this.v1=e,this.v2=t}getPoint(e,t=new H){let n=t;return e===1?n.copy(this.v2):(n.copy(this.v2).sub(this.v1),n.multiplyScalar(e).add(this.v1)),n}getPointAt(e,t){return this.getPoint(e,t)}getTangent(e,t=new H){return t.subVectors(this.v2,this.v1).normalize()}getTangentAt(e,t){return this.getTangent(e,t)}copy(e){return super.copy(e),this.v1.copy(e.v1),this.v2.copy(e.v2),this}toJSON(){let e=super.toJSON();return e.v1=this.v1.toArray(),e.v2=this.v2.toArray(),e}fromJSON(e){return super.fromJSON(e),this.v1.fromArray(e.v1),this.v2.fromArray(e.v2),this}},Ku=class extends Su{constructor(e=new V,t=new V,n=new V){super(),this.isQuadraticBezierCurve=!0,this.type=`QuadraticBezierCurve`,this.v0=e,this.v1=t,this.v2=n}getPoint(e,t=new V){let n=t,r=this.v0,i=this.v1,a=this.v2;return n.set(Iu(e,r.x,i.x,a.x),Iu(e,r.y,i.y,a.y)),n}copy(e){return super.copy(e),this.v0.copy(e.v0),this.v1.copy(e.v1),this.v2.copy(e.v2),this}toJSON(){let e=super.toJSON();return e.v0=this.v0.toArray(),e.v1=this.v1.toArray(),e.v2=this.v2.toArray(),e}fromJSON(e){return super.fromJSON(e),this.v0.fromArray(e.v0),this.v1.fromArray(e.v1),this.v2.fromArray(e.v2),this}},qu=class extends Su{constructor(e=new H,t=new H,n=new H){super(),this.isQuadraticBezierCurve3=!0,this.type=`QuadraticBezierCurve3`,this.v0=e,this.v1=t,this.v2=n}getPoint(e,t=new H){let n=t,r=this.v0,i=this.v1,a=this.v2;return n.set(Iu(e,r.x,i.x,a.x),Iu(e,r.y,i.y,a.y),Iu(e,r.z,i.z,a.z)),n}copy(e){return super.copy(e),this.v0.copy(e.v0),this.v1.copy(e.v1),this.v2.copy(e.v2),this}toJSON(){let e=super.toJSON();return e.v0=this.v0.toArray(),e.v1=this.v1.toArray(),e.v2=this.v2.toArray(),e}fromJSON(e){return super.fromJSON(e),this.v0.fromArray(e.v0),this.v1.fromArray(e.v1),this.v2.fromArray(e.v2),this}},Ju=Object.freeze({__proto__:null,ArcCurve:wu,CatmullRomCurve3:ju,CubicBezierCurve:Hu,CubicBezierCurve3:Uu,EllipseCurve:Cu,LineCurve:Wu,LineCurve3:Gu,QuadraticBezierCurve:Ku,QuadraticBezierCurve3:qu,SplineCurve:class extends Su{constructor(e=[]){super(),this.isSplineCurve=!0,this.type=`SplineCurve`,this.points=e}getPoint(e,t=new V){let n=t,r=this.points,i=(r.length-1)*e,a=Math.floor(i),o=i-a,s=r[a===0?a:a-1],c=r[a],l=r[a>r.length-2?r.length-1:a+1],u=r[a>r.length-3?r.length-1:a+2];return n.set(Mu(o,s.x,c.x,l.x,u.x),Mu(o,s.y,c.y,l.y,u.y)),n}copy(e){super.copy(e),this.points=[];for(let t=0,n=e.points.length;t<n;t++){let n=e.points[t];this.points.push(n.clone())}return this}toJSON(){let e=super.toJSON();e.points=[];for(let t=0,n=this.points.length;t<n;t++){let n=this.points[t];e.points.push(n.toArray())}return e}fromJSON(e){super.fromJSON(e),this.points=[];for(let t=0,n=e.points.length;t<n;t++){let n=e.points[t];this.points.push(new V().fromArray(n))}return this}}}),Yu=class e extends Vc{constructor(e=1,t=1,n=1,r=1){super(),this.type=`PlaneGeometry`,this.parameters={width:e,height:t,widthSegments:n,heightSegments:r};let i=e/2,a=t/2,o=Math.floor(n),s=Math.floor(r),c=o+1,l=s+1,u=e/o,d=t/s,f=[],p=[],m=[],h=[];for(let e=0;e<l;e++){let t=e*d-a;for(let n=0;n<c;n++){let r=n*u-i;p.push(r,-t,0),m.push(0,0,1),h.push(n/o),h.push(1-e/s)}}for(let e=0;e<s;e++)for(let t=0;t<o;t++){let n=t+c*e,r=t+c*(e+1),i=t+1+c*(e+1),a=t+1+c*e;f.push(n,r,a),f.push(r,i,a)}this.setIndex(f),this.setAttribute(`position`,new G(p,3)),this.setAttribute(`normal`,new G(m,3)),this.setAttribute(`uv`,new G(h,2))}copy(e){return super.copy(e),this.parameters=Object.assign({},e.parameters),this}static fromJSON(t){return new e(t.width,t.height,t.widthSegments,t.heightSegments)}},Xu=class e extends Vc{constructor(e=.5,t=1,n=32,r=1,i=0,a=Math.PI*2){super(),this.type=`RingGeometry`,this.parameters={innerRadius:e,outerRadius:t,thetaSegments:n,phiSegments:r,thetaStart:i,thetaLength:a},n=Math.max(3,n),r=Math.max(1,r);let o=[],s=[],c=[],l=[],u=e,d=(t-e)/r,f=new H,p=new V;for(let e=0;e<=r;e++){for(let e=0;e<=n;e++){let r=i+e/n*a;f.x=u*Math.cos(r),f.y=u*Math.sin(r),s.push(f.x,f.y,f.z),c.push(0,0,1),p.x=(f.x/t+1)/2,p.y=(f.y/t+1)/2,l.push(p.x,p.y)}u+=d}for(let e=0;e<r;e++){let t=e*(n+1);for(let e=0;e<n;e++){let r=e+t,i=r,a=r+n+1,s=r+n+2,c=r+1;o.push(i,a,c),o.push(a,s,c)}}this.setIndex(o),this.setAttribute(`position`,new G(s,3)),this.setAttribute(`normal`,new G(c,3)),this.setAttribute(`uv`,new G(l,2))}copy(e){return super.copy(e),this.parameters=Object.assign({},e.parameters),this}static fromJSON(t){return new e(t.innerRadius,t.outerRadius,t.thetaSegments,t.phiSegments,t.thetaStart,t.thetaLength)}},Zu=class e extends Vc{constructor(e=1,t=32,n=16,r=0,i=Math.PI*2,a=0,o=Math.PI){super(),this.type=`SphereGeometry`,this.parameters={radius:e,widthSegments:t,heightSegments:n,phiStart:r,phiLength:i,thetaStart:a,thetaLength:o},t=Math.max(3,Math.floor(t)),n=Math.max(2,Math.floor(n));let s=Math.min(a+o,Math.PI),c=0,l=[],u=new H,d=new H,f=[],p=[],m=[],h=[];for(let f=0;f<=n;f++){let g=[],_=f/n,v=0;f===0&&a===0?v=.5/t:f===n&&s===Math.PI&&(v=-.5/t);for(let n=0;n<=t;n++){let s=n/t;u.x=-e*Math.cos(r+s*i)*Math.sin(a+_*o),u.y=e*Math.cos(a+_*o),u.z=e*Math.sin(r+s*i)*Math.sin(a+_*o),p.push(u.x,u.y,u.z),d.copy(u).normalize(),m.push(d.x,d.y,d.z),h.push(s+v,1-_),g.push(c++)}l.push(g)}for(let e=0;e<n;e++)for(let r=0;r<t;r++){let t=l[e][r+1],i=l[e][r],o=l[e+1][r],c=l[e+1][r+1];(e!==0||a>0)&&f.push(t,i,c),(e!==n-1||s<Math.PI)&&f.push(i,o,c)}this.setIndex(f),this.setAttribute(`position`,new G(p,3)),this.setAttribute(`normal`,new G(m,3)),this.setAttribute(`uv`,new G(h,2))}copy(e){return super.copy(e),this.parameters=Object.assign({},e.parameters),this}static fromJSON(t){return new e(t.radius,t.widthSegments,t.heightSegments,t.phiStart,t.phiLength,t.thetaStart,t.thetaLength)}},Qu=class e extends Vc{constructor(e=1,t=.4,n=12,r=48,i=Math.PI*2,a=0,o=Math.PI*2){super(),this.type=`TorusGeometry`,this.parameters={radius:e,tube:t,radialSegments:n,tubularSegments:r,arc:i,thetaStart:a,thetaLength:o},n=Math.floor(n),r=Math.floor(r);let s=[],c=[],l=[],u=[],d=new H,f=new H,p=new H;for(let s=0;s<=n;s++){let m=a+s/n*o;for(let a=0;a<=r;a++){let o=a/r*i;f.x=(e+t*Math.cos(m))*Math.cos(o),f.y=(e+t*Math.cos(m))*Math.sin(o),f.z=t*Math.sin(m),c.push(f.x,f.y,f.z),d.x=e*Math.cos(o),d.y=e*Math.sin(o),p.subVectors(f,d).normalize(),l.push(p.x,p.y,p.z),u.push(a/r),u.push(s/n)}}for(let e=1;e<=n;e++)for(let t=1;t<=r;t++){let n=(r+1)*e+t-1,i=(r+1)*(e-1)+t-1,a=(r+1)*(e-1)+t,o=(r+1)*e+t;s.push(n,i,o),s.push(i,a,o)}this.setIndex(s),this.setAttribute(`position`,new G(c,3)),this.setAttribute(`normal`,new G(l,3)),this.setAttribute(`uv`,new G(u,2))}copy(e){return super.copy(e),this.parameters=Object.assign({},e.parameters),this}static fromJSON(t){return new e(t.radius,t.tube,t.radialSegments,t.tubularSegments,t.arc)}},$u=class e extends Vc{constructor(e=new qu(new H(-1,-1,0),new H(-1,1,0),new H(1,1,0)),t=64,n=1,r=8,i=!1){super(),this.type=`TubeGeometry`,this.parameters={path:e,tubularSegments:t,radius:n,radialSegments:r,closed:i};let a=e.computeFrenetFrames(t,i);this.tangents=a.tangents,this.normals=a.normals,this.binormals=a.binormals;let o=new H,s=new H,c=new V,l=new H,u=[],d=[],f=[],p=[];m(),this.setIndex(p),this.setAttribute(`position`,new G(u,3)),this.setAttribute(`normal`,new G(d,3)),this.setAttribute(`uv`,new G(f,2));function m(){for(let e=0;e<t;e++)h(e);h(i===!1?t:0),_(),g()}function h(i){l=e.getPointAt(i/t,l);let c=a.normals[i],f=a.binormals[i];for(let e=0;e<=r;e++){let t=e/r*Math.PI*2,i=Math.sin(t),a=-Math.cos(t);s.x=a*c.x+i*f.x,s.y=a*c.y+i*f.y,s.z=a*c.z+i*f.z,s.normalize(),d.push(s.x,s.y,s.z),o.x=l.x+n*s.x,o.y=l.y+n*s.y,o.z=l.z+n*s.z,u.push(o.x,o.y,o.z)}}function g(){for(let e=1;e<=t;e++)for(let t=1;t<=r;t++){let n=(r+1)*(e-1)+(t-1),i=(r+1)*e+(t-1),a=(r+1)*e+t,o=(r+1)*(e-1)+t;p.push(n,i,o),p.push(i,a,o)}}function _(){for(let e=0;e<=t;e++)for(let n=0;n<=r;n++)c.x=e/t,c.y=n/r,f.push(c.x,c.y)}}copy(e){return super.copy(e),this.parameters=Object.assign({},e.parameters),this}toJSON(){let e=super.toJSON();return e.path=this.parameters.path.toJSON(),e}static fromJSON(t){return new e(new Ju[t.path.type]().fromJSON(t.path),t.tubularSegments,t.radius,t.radialSegments,t.closed)}},ed=class extends Vc{constructor(e=null){if(super(),this.type=`WireframeGeometry`,this.parameters={geometry:e},e!==null){let t=[],n=new Set,r=new H,i=new H;if(e.index!==null){let a=e.attributes.position,o=e.index,s=e.groups;s.length===0&&(s=[{start:0,count:o.count,materialIndex:0}]);for(let e=0,c=s.length;e<c;++e){let c=s[e],l=c.start,u=c.count;for(let e=l,s=l+u;e<s;e+=3)for(let s=0;s<3;s++){let c=o.getX(e+s),l=o.getX(e+(s+1)%3);r.fromBufferAttribute(a,c),i.fromBufferAttribute(a,l),td(r,i,n)===!0&&(t.push(r.x,r.y,r.z),t.push(i.x,i.y,i.z))}}}else{let a=e.attributes.position;for(let e=0,o=a.count/3;e<o;e++)for(let o=0;o<3;o++){let s=3*e+o,c=3*e+(o+1)%3;r.fromBufferAttribute(a,s),i.fromBufferAttribute(a,c),td(r,i,n)===!0&&(t.push(r.x,r.y,r.z),t.push(i.x,i.y,i.z))}}this.setAttribute(`position`,new G(t,3))}}copy(e){return super.copy(e),this.parameters=Object.assign({},e.parameters),this}};function td(e,t,n){let r=`${e.x},${e.y},${e.z}-${t.x},${t.y},${t.z}`,i=`${t.x},${t.y},${t.z}-${e.x},${e.y},${e.z}`;return n.has(r)===!0||n.has(i)===!0?!1:(n.add(r),n.add(i),!0)}function nd(e){let t={};for(let n in e){t[n]={};for(let r in e[n]){let i=e[n][r];if(id(i))i.isRenderTargetTexture?(R(`UniformsUtils: Textures of render targets cannot be cloned via cloneUniforms() or mergeUniforms().`),t[n][r]=null):t[n][r]=i.clone();else if(Array.isArray(i))if(id(i[0])){let e=[];for(let t=0,n=i.length;t<n;t++)e[t]=i[t].clone();t[n][r]=e}else t[n][r]=i.slice();else t[n][r]=i}}return t}function rd(e){let t={};for(let n=0;n<e.length;n++){let r=nd(e[n]);for(let e in r)t[e]=r[e]}return t}function id(e){return e&&(e.isColor||e.isMatrix3||e.isMatrix4||e.isVector2||e.isVector3||e.isVector4||e.isTexture||e.isQuaternion)}function ad(e){let t=[];for(let n=0;n<e.length;n++)t.push(e[n].clone());return t}function od(e){let t=e.getRenderTarget();return t===null?e.outputColorSpace:t.isXRRenderTarget===!0?t.texture.colorSpace:Xo.workingColorSpace}var sd={clone:nd,merge:rd},cd=`void main() {
	gl_Position = projectionMatrix * modelViewMatrix * vec4( position, 1.0 );
}`,ld=`void main() {
	gl_FragColor = vec4( 1.0, 0.0, 0.0, 1.0 );
}`,ud=class extends Kc{constructor(e){super(),this.isShaderMaterial=!0,this.type=`ShaderMaterial`,this.defines={},this.uniforms={},this.uniformsGroups=[],this.vertexShader=cd,this.fragmentShader=ld,this.linewidth=1,this.wireframe=!1,this.wireframeLinewidth=1,this.fog=!1,this.lights=!1,this.clipping=!1,this.forceSinglePass=!0,this.extensions={clipCullDistance:!1,multiDraw:!1},this.defaultAttributeValues={color:[1,1,1],uv:[0,0],uv1:[0,0]},this.index0AttributeName=void 0,this.uniformsNeedUpdate=!1,this.glslVersion=null,e!==void 0&&this.setValues(e)}copy(e){return super.copy(e),this.fragmentShader=e.fragmentShader,this.vertexShader=e.vertexShader,this.uniforms=nd(e.uniforms),this.uniformsGroups=ad(e.uniformsGroups),this.defines=Object.assign({},e.defines),this.wireframe=e.wireframe,this.wireframeLinewidth=e.wireframeLinewidth,this.fog=e.fog,this.lights=e.lights,this.clipping=e.clipping,this.extensions=Object.assign({},e.extensions),this.glslVersion=e.glslVersion,this.defaultAttributeValues=Object.assign({},e.defaultAttributeValues),this.index0AttributeName=e.index0AttributeName,this.uniformsNeedUpdate=e.uniformsNeedUpdate,this}toJSON(e){let t=super.toJSON(e);t.glslVersion=this.glslVersion,t.uniforms={};for(let n in this.uniforms){let r=this.uniforms[n].value;r&&r.isTexture?t.uniforms[n]={type:`t`,value:r.toJSON(e).uuid}:r&&r.isColor?t.uniforms[n]={type:`c`,value:r.getHex()}:r&&r.isVector2?t.uniforms[n]={type:`v2`,value:r.toArray()}:r&&r.isVector3?t.uniforms[n]={type:`v3`,value:r.toArray()}:r&&r.isVector4?t.uniforms[n]={type:`v4`,value:r.toArray()}:r&&r.isMatrix3?t.uniforms[n]={type:`m3`,value:r.toArray()}:r&&r.isMatrix4?t.uniforms[n]={type:`m4`,value:r.toArray()}:t.uniforms[n]={value:r}}Object.keys(this.defines).length>0&&(t.defines=this.defines),t.vertexShader=this.vertexShader,t.fragmentShader=this.fragmentShader,t.lights=this.lights,t.clipping=this.clipping;let n={};for(let e in this.extensions)this.extensions[e]===!0&&(n[e]=!0);return Object.keys(n).length>0&&(t.extensions=n),t}},dd=class extends ud{constructor(e){super(e),this.isRawShaderMaterial=!0,this.type=`RawShaderMaterial`}},fd=class extends Kc{constructor(e){super(),this.isMeshStandardMaterial=!0,this.type=`MeshStandardMaterial`,this.defines={STANDARD:``},this.color=new W(16777215),this.roughness=1,this.metalness=0,this.map=null,this.lightMap=null,this.lightMapIntensity=1,this.aoMap=null,this.aoMapIntensity=1,this.emissive=new W(0),this.emissiveIntensity=1,this.emissiveMap=null,this.bumpMap=null,this.bumpScale=1,this.normalMap=null,this.normalMapType=0,this.normalScale=new V(1,1),this.displacementMap=null,this.displacementScale=1,this.displacementBias=0,this.roughnessMap=null,this.metalnessMap=null,this.alphaMap=null,this.envMap=null,this.envMapRotation=new Ss,this.envMapIntensity=1,this.wireframe=!1,this.wireframeLinewidth=1,this.wireframeLinecap=`round`,this.wireframeLinejoin=`round`,this.flatShading=!1,this.fog=!0,this.setValues(e)}copy(e){return super.copy(e),this.defines={STANDARD:``},this.color.copy(e.color),this.roughness=e.roughness,this.metalness=e.metalness,this.map=e.map,this.lightMap=e.lightMap,this.lightMapIntensity=e.lightMapIntensity,this.aoMap=e.aoMap,this.aoMapIntensity=e.aoMapIntensity,this.emissive.copy(e.emissive),this.emissiveMap=e.emissiveMap,this.emissiveIntensity=e.emissiveIntensity,this.bumpMap=e.bumpMap,this.bumpScale=e.bumpScale,this.normalMap=e.normalMap,this.normalMapType=e.normalMapType,this.normalScale.copy(e.normalScale),this.displacementMap=e.displacementMap,this.displacementScale=e.displacementScale,this.displacementBias=e.displacementBias,this.roughnessMap=e.roughnessMap,this.metalnessMap=e.metalnessMap,this.alphaMap=e.alphaMap,this.envMap=e.envMap,this.envMapRotation.copy(e.envMapRotation),this.envMapIntensity=e.envMapIntensity,this.wireframe=e.wireframe,this.wireframeLinewidth=e.wireframeLinewidth,this.wireframeLinecap=e.wireframeLinecap,this.wireframeLinejoin=e.wireframeLinejoin,this.flatShading=e.flatShading,this.fog=e.fog,this}},pd=class extends Kc{constructor(e){super(),this.isMeshDepthMaterial=!0,this.type=`MeshDepthMaterial`,this.depthPacking=Ya,this.map=null,this.alphaMap=null,this.displacementMap=null,this.displacementScale=1,this.displacementBias=0,this.wireframe=!1,this.wireframeLinewidth=1,this.setValues(e)}copy(e){return super.copy(e),this.depthPacking=e.depthPacking,this.map=e.map,this.alphaMap=e.alphaMap,this.displacementMap=e.displacementMap,this.displacementScale=e.displacementScale,this.displacementBias=e.displacementBias,this.wireframe=e.wireframe,this.wireframeLinewidth=e.wireframeLinewidth,this}},md=class extends Kc{constructor(e){super(),this.isMeshDistanceMaterial=!0,this.type=`MeshDistanceMaterial`,this.map=null,this.alphaMap=null,this.displacementMap=null,this.displacementScale=1,this.displacementBias=0,this.setValues(e)}copy(e){return super.copy(e),this.map=e.map,this.alphaMap=e.alphaMap,this.displacementMap=e.displacementMap,this.displacementScale=e.displacementScale,this.displacementBias=e.displacementBias,this}},hd=class extends Xl{constructor(e){super(),this.isLineDashedMaterial=!0,this.type=`LineDashedMaterial`,this.scale=1,this.dashSize=3,this.gapSize=1,this.setValues(e)}copy(e){return super.copy(e),this.scale=e.scale,this.dashSize=e.dashSize,this.gapSize=e.gapSize,this}};function gd(e,t){return!e||e.constructor===t?e:typeof t.BYTES_PER_ELEMENT==`number`?new t(e):Array.prototype.slice.call(e)}var _d=class{constructor(e,t,n,r){this.parameterPositions=e,this._cachedIndex=0,this.resultBuffer=r===void 0?new t.constructor(n):r,this.sampleValues=t,this.valueSize=n,this.settings=null,this.DefaultSettings_={}}evaluate(e){let t=this.parameterPositions,n=this._cachedIndex,r=t[n],i=t[n-1];validate_interval:{seek:{let a;linear_scan:{forward_scan:if(!(e<r)){for(let a=n+2;;){if(r===void 0){if(e<i)break forward_scan;return n=t.length,this._cachedIndex=n,this.copySampleValue_(n-1)}if(n===a)break;if(i=r,r=t[++n],e<r)break seek}a=t.length;break linear_scan}if(!(e>=i)){let o=t[1];e<o&&(n=2,i=o);for(let a=n-2;;){if(i===void 0)return this._cachedIndex=0,this.copySampleValue_(0);if(n===a)break;if(r=i,i=t[--n-1],e>=i)break seek}a=n,n=0;break linear_scan}break validate_interval}for(;n<a;){let r=n+a>>>1;e<t[r]?a=r:n=r+1}if(r=t[n],i=t[n-1],i===void 0)return this._cachedIndex=0,this.copySampleValue_(0);if(r===void 0)return n=t.length,this._cachedIndex=n,this.copySampleValue_(n-1)}this._cachedIndex=n,this.intervalChanged_(n,i,r)}return this.interpolate_(n,i,e,r)}getSettings_(){return this.settings||this.DefaultSettings_}copySampleValue_(e){let t=this.resultBuffer,n=this.sampleValues,r=this.valueSize,i=e*r;for(let e=0;e!==r;++e)t[e]=n[i+e];return t}interpolate_(){throw Error(`call to abstract method`)}intervalChanged_(){}},vd=class extends _d{constructor(e,t,n,r){super(e,t,n,r),this._weightPrev=-0,this._offsetPrev=-0,this._weightNext=-0,this._offsetNext=-0,this.DefaultSettings_={endingStart:Ka,endingEnd:Ka}}intervalChanged_(e,t,n){let r=this.parameterPositions,i=e-2,a=e+1,o=r[i],s=r[a];if(o===void 0)switch(this.getSettings_().endingStart){case qa:i=e,o=2*t-n;break;case Ja:i=r.length-2,o=t+r[i]-r[i+1];break;default:i=e,o=n}if(s===void 0)switch(this.getSettings_().endingEnd){case qa:a=e,s=2*n-t;break;case Ja:a=1,s=n+r[1]-r[0];break;default:a=e-1,s=t}let c=(n-t)*.5,l=this.valueSize;this._weightPrev=c/(t-o),this._weightNext=c/(s-n),this._offsetPrev=i*l,this._offsetNext=a*l}interpolate_(e,t,n,r){let i=this.resultBuffer,a=this.sampleValues,o=this.valueSize,s=e*o,c=s-o,l=this._offsetPrev,u=this._offsetNext,d=this._weightPrev,f=this._weightNext,p=(n-t)/(r-t),m=p*p,h=m*p,g=-d*h+2*d*m-d*p,_=(1+d)*h+(-1.5-2*d)*m+(-.5+d)*p+1,v=(-1-f)*h+(1.5+f)*m+.5*p,y=f*h-f*m;for(let e=0;e!==o;++e)i[e]=g*a[l+e]+_*a[c+e]+v*a[s+e]+y*a[u+e];return i}},yd=class extends _d{constructor(e,t,n,r){super(e,t,n,r)}interpolate_(e,t,n,r){let i=this.resultBuffer,a=this.sampleValues,o=this.valueSize,s=e*o,c=s-o,l=(n-t)/(r-t),u=1-l;for(let e=0;e!==o;++e)i[e]=a[c+e]*u+a[s+e]*l;return i}},bd=class extends _d{constructor(e,t,n,r){super(e,t,n,r)}interpolate_(e){return this.copySampleValue_(e-1)}},xd=class extends _d{interpolate_(e,t,n,r){let i=this.resultBuffer,a=this.sampleValues,o=this.valueSize,s=e*o,c=s-o,l=this.settings||this.DefaultSettings_,u=l.inTangents,d=l.outTangents;if(!u||!d){let e=(n-t)/(r-t),l=1-e;for(let t=0;t!==o;++t)i[t]=a[c+t]*l+a[s+t]*e;return i}let f=o*2,p=e-1;for(let l=0;l!==o;++l){let o=a[c+l],m=a[s+l],h=p*f+l*2,g=d[h],_=d[h+1],v=e*f+l*2,y=u[v],b=u[v+1],x=(n-t)/(r-t),S,C,w,T,E;for(let e=0;e<8;e++){S=x*x,C=S*x,w=1-x,T=w*w,E=T*w;let e=E*t+3*T*x*g+3*w*S*y+C*r-n;if(Math.abs(e)<1e-10)break;let i=3*T*(g-t)+6*w*x*(y-g)+3*S*(r-y);if(Math.abs(i)<1e-10)break;x-=e/i,x=Math.max(0,Math.min(1,x))}i[l]=E*o+3*T*x*_+3*w*S*b+C*m}return i}},Sd=class{constructor(e,t,n,r){if(e===void 0)throw Error(`THREE.KeyframeTrack: track name is undefined`);if(t===void 0||t.length===0)throw Error(`THREE.KeyframeTrack: no keyframes in track named `+e);this.name=e,this.times=gd(t,this.TimeBufferType),this.values=gd(n,this.ValueBufferType),this.setInterpolation(r||this.DefaultInterpolation)}static toJSON(e){let t=e.constructor,n;if(t.toJSON!==this.toJSON)n=t.toJSON(e);else{n={name:e.name,times:gd(e.times,Array),values:gd(e.values,Array)};let t=e.getInterpolation();t!==e.DefaultInterpolation&&(n.interpolation=t)}return n.type=e.ValueTypeName,n}InterpolantFactoryMethodDiscrete(e){return new bd(this.times,this.values,this.getValueSize(),e)}InterpolantFactoryMethodLinear(e){return new yd(this.times,this.values,this.getValueSize(),e)}InterpolantFactoryMethodSmooth(e){return new vd(this.times,this.values,this.getValueSize(),e)}InterpolantFactoryMethodBezier(e){let t=new xd(this.times,this.values,this.getValueSize(),e);return this.settings&&(t.settings=this.settings),t}setInterpolation(e){let t;switch(e){case Ha:t=this.InterpolantFactoryMethodDiscrete;break;case Ua:t=this.InterpolantFactoryMethodLinear;break;case Wa:t=this.InterpolantFactoryMethodSmooth;break;case Ga:t=this.InterpolantFactoryMethodBezier;break}if(t===void 0){let t=`unsupported interpolation for `+this.ValueTypeName+` keyframe track named `+this.name;if(this.createInterpolant===void 0)if(e!==this.DefaultInterpolation)this.setInterpolation(this.DefaultInterpolation);else throw Error(t);return R(`KeyframeTrack:`,t),this}return this.createInterpolant=t,this}getInterpolation(){switch(this.createInterpolant){case this.InterpolantFactoryMethodDiscrete:return Ha;case this.InterpolantFactoryMethodLinear:return Ua;case this.InterpolantFactoryMethodSmooth:return Wa;case this.InterpolantFactoryMethodBezier:return Ga}}getValueSize(){return this.values.length/this.times.length}shift(e){if(e!==0){let t=this.times;for(let n=0,r=t.length;n!==r;++n)t[n]+=e}return this}scale(e){if(e!==1){let t=this.times;for(let n=0,r=t.length;n!==r;++n)t[n]*=e}return this}trim(e,t){let n=this.times,r=n.length,i=0,a=r-1;for(;i!==r&&n[i]<e;)++i;for(;a!==-1&&n[a]>t;)--a;if(++a,i!==0||a!==r){i>=a&&(a=Math.max(a,1),i=a-1);let e=this.getValueSize();this.times=n.slice(i,a),this.values=this.values.slice(i*e,a*e)}return this}validate(){let e=!0,t=this.getValueSize();t-Math.floor(t)!==0&&(z(`KeyframeTrack: Invalid value size in track.`,this),e=!1);let n=this.times,r=this.values,i=n.length;i===0&&(z(`KeyframeTrack: Track is empty.`,this),e=!1);let a=null;for(let t=0;t!==i;t++){let r=n[t];if(typeof r==`number`&&isNaN(r)){z(`KeyframeTrack: Time is not a valid number.`,this,t,r),e=!1;break}if(a!==null&&a>r){z(`KeyframeTrack: Out of order keys.`,this,t,r,a),e=!1;break}a=r}if(r!==void 0&&ao(r))for(let t=0,n=r.length;t!==n;++t){let n=r[t];if(isNaN(n)){z(`KeyframeTrack: Value is not a valid number.`,this,t,n),e=!1;break}}return e}optimize(){let e=this.times.slice(),t=this.values.slice(),n=this.getValueSize(),r=this.getInterpolation()===Wa,i=e.length-1,a=1;for(let o=1;o<i;++o){let i=!1,s=e[o];if(s!==e[o+1]&&(o!==1||s!==e[0]))if(r)i=!0;else{let e=o*n,r=e-n,a=e+n;for(let o=0;o!==n;++o){let n=t[e+o];if(n!==t[r+o]||n!==t[a+o]){i=!0;break}}}if(i){if(o!==a){e[a]=e[o];let r=o*n,i=a*n;for(let e=0;e!==n;++e)t[i+e]=t[r+e]}++a}}if(i>0){e[a]=e[i];for(let e=i*n,r=a*n,o=0;o!==n;++o)t[r+o]=t[e+o];++a}return a===e.length?(this.times=e,this.values=t):(this.times=e.slice(0,a),this.values=t.slice(0,a*n)),this}clone(){let e=this.times.slice(),t=this.values.slice(),n=this.constructor,r=new n(this.name,e,t);return r.createInterpolant=this.createInterpolant,r}};Sd.prototype.ValueTypeName=``,Sd.prototype.TimeBufferType=Float32Array,Sd.prototype.ValueBufferType=Float32Array,Sd.prototype.DefaultInterpolation=Ua;var Cd=class extends Sd{constructor(e,t,n){super(e,t,n)}};Cd.prototype.ValueTypeName=`bool`,Cd.prototype.ValueBufferType=Array,Cd.prototype.DefaultInterpolation=Ha,Cd.prototype.InterpolantFactoryMethodLinear=void 0,Cd.prototype.InterpolantFactoryMethodSmooth=void 0;var wd=class extends Sd{constructor(e,t,n,r){super(e,t,n,r)}};wd.prototype.ValueTypeName=`color`;var Td=class extends Sd{constructor(e,t,n,r){super(e,t,n,r)}};Td.prototype.ValueTypeName=`number`;var Ed=class extends _d{constructor(e,t,n,r){super(e,t,n,r)}interpolate_(e,t,n,r){let i=this.resultBuffer,a=this.sampleValues,o=this.valueSize,s=(n-t)/(r-t),c=e*o;for(let e=c+o;c!==e;c+=4)Uo.slerpFlat(i,0,a,c-o,a,c,s);return i}},Dd=class extends Sd{constructor(e,t,n,r){super(e,t,n,r)}InterpolantFactoryMethodLinear(e){return new Ed(this.times,this.values,this.getValueSize(),e)}};Dd.prototype.ValueTypeName=`quaternion`,Dd.prototype.InterpolantFactoryMethodSmooth=void 0;var Od=class extends Sd{constructor(e,t,n){super(e,t,n)}};Od.prototype.ValueTypeName=`string`,Od.prototype.ValueBufferType=Array,Od.prototype.DefaultInterpolation=Ha,Od.prototype.InterpolantFactoryMethodLinear=void 0,Od.prototype.InterpolantFactoryMethodSmooth=void 0;var kd=class extends Sd{constructor(e,t,n,r){super(e,t,n,r)}};kd.prototype.ValueTypeName=`vector`;var Ad=new class{constructor(e,t,n){let r=this,i=!1,a=0,o=0,s,c=[];this.onStart=void 0,this.onLoad=e,this.onProgress=t,this.onError=n,this._abortController=null,this.itemStart=function(e){o++,i===!1&&r.onStart!==void 0&&r.onStart(e,a,o),i=!0},this.itemEnd=function(e){a++,r.onProgress!==void 0&&r.onProgress(e,a,o),a===o&&(i=!1,r.onLoad!==void 0&&r.onLoad())},this.itemError=function(e){r.onError!==void 0&&r.onError(e)},this.resolveURL=function(e){return s?s(e):e},this.setURLModifier=function(e){return s=e,this},this.addHandler=function(e,t){return c.push(e,t),this},this.removeHandler=function(e){let t=c.indexOf(e);return t!==-1&&c.splice(t,2),this},this.getHandler=function(e){for(let t=0,n=c.length;t<n;t+=2){let n=c[t],r=c[t+1];if(n.global&&(n.lastIndex=0),n.test(e))return r}return null},this.abort=function(){return this.abortController.abort(),this._abortController=null,this}}get abortController(){return this._abortController||=new AbortController,this._abortController}},jd=class{constructor(e){this.manager=e===void 0?Ad:e,this.crossOrigin=`anonymous`,this.withCredentials=!1,this.path=``,this.resourcePath=``,this.requestHeader={},typeof __THREE_DEVTOOLS__<`u`&&__THREE_DEVTOOLS__.dispatchEvent(new CustomEvent(`observe`,{detail:this}))}load(){}loadAsync(e,t){let n=this;return new Promise(function(r,i){n.load(e,r,t,i)})}parse(){}setCrossOrigin(e){return this.crossOrigin=e,this}setWithCredentials(e){return this.withCredentials=e,this}setPath(e){return this.path=e,this}setResourcePath(e){return this.resourcePath=e,this}setRequestHeader(e){return this.requestHeader=e,this}abort(){return this}};jd.DEFAULT_MATERIAL_NAME=`__DEFAULT`;var Md=class extends zs{constructor(e,t=1){super(),this.isLight=!0,this.type=`Light`,this.color=new W(e),this.intensity=t}dispose(){this.dispatchEvent({type:`dispose`})}copy(e,t){return super.copy(e,t),this.color.copy(e.color),this.intensity=e.intensity,this}toJSON(e){let t=super.toJSON(e);return t.object.color=this.color.getHex(),t.object.intensity=this.intensity,t}},Nd=class extends Md{constructor(e,t,n){super(e,n),this.isHemisphereLight=!0,this.type=`HemisphereLight`,this.position.copy(zs.DEFAULT_UP),this.updateMatrix(),this.groundColor=new W(t)}copy(e,t){return super.copy(e,t),this.groundColor.copy(e.groundColor),this}toJSON(e){let t=super.toJSON(e);return t.object.groundColor=this.groundColor.getHex(),t}},Pd=new fs,Fd=new H,Id=new H,Ld=class{constructor(e){this.camera=e,this.intensity=1,this.bias=0,this.biasNode=null,this.normalBias=0,this.radius=1,this.blurSamples=8,this.mapSize=new V(512,512),this.mapType=Li,this.map=null,this.mapPass=null,this.matrix=new fs,this.autoUpdate=!0,this.needsUpdate=!1,this._frustum=new Yl,this._frameExtents=new V(1,1),this._viewportCount=1,this._viewports=[new ss(0,0,1,1)]}getViewportCount(){return this._viewportCount}getFrustum(){return this._frustum}updateMatrices(e){let t=this.camera,n=this.matrix;Fd.setFromMatrixPosition(e.matrixWorld),t.position.copy(Fd),Id.setFromMatrixPosition(e.target.matrixWorld),t.lookAt(Id),t.updateMatrixWorld(),Pd.multiplyMatrices(t.projectionMatrix,t.matrixWorldInverse),this._frustum.setFromProjectionMatrix(Pd,t.coordinateSystem,t.reversedDepth),t.coordinateSystem===2001||t.reversedDepth?n.set(.5,0,0,.5,0,.5,0,.5,0,0,1,0,0,0,0,1):n.set(.5,0,0,.5,0,.5,0,.5,0,0,.5,.5,0,0,0,1),n.multiply(Pd)}getViewport(e){return this._viewports[e]}getFrameExtents(){return this._frameExtents}dispose(){this.map&&this.map.dispose(),this.mapPass&&this.mapPass.dispose()}copy(e){return this.camera=e.camera.clone(),this.intensity=e.intensity,this.bias=e.bias,this.radius=e.radius,this.autoUpdate=e.autoUpdate,this.needsUpdate=e.needsUpdate,this.normalBias=e.normalBias,this.blurSamples=e.blurSamples,this.mapSize.copy(e.mapSize),this.biasNode=e.biasNode,this}clone(){return new this.constructor().copy(this)}toJSON(){let e={};return this.intensity!==1&&(e.intensity=this.intensity),this.bias!==0&&(e.bias=this.bias),this.normalBias!==0&&(e.normalBias=this.normalBias),this.radius!==1&&(e.radius=this.radius),(this.mapSize.x!==512||this.mapSize.y!==512)&&(e.mapSize=this.mapSize.toArray()),e.camera=this.camera.toJSON(!1).object,delete e.camera.matrix,e}},Rd=new H,zd=new Uo,Bd=new H,Vd=class extends zs{constructor(){super(),this.isCamera=!0,this.type=`Camera`,this.matrixWorldInverse=new fs,this.projectionMatrix=new fs,this.projectionMatrixInverse=new fs,this.coordinateSystem=ro,this._reversedDepth=!1}get reversedDepth(){return this._reversedDepth}copy(e,t){return super.copy(e,t),this.matrixWorldInverse.copy(e.matrixWorldInverse),this.projectionMatrix.copy(e.projectionMatrix),this.projectionMatrixInverse.copy(e.projectionMatrixInverse),this.coordinateSystem=e.coordinateSystem,this}getWorldDirection(e){return super.getWorldDirection(e).negate()}updateMatrixWorld(e){super.updateMatrixWorld(e),this.matrixWorld.decompose(Rd,zd,Bd),Bd.x===1&&Bd.y===1&&Bd.z===1?this.matrixWorldInverse.copy(this.matrixWorld).invert():this.matrixWorldInverse.compose(Rd,zd,Bd.set(1,1,1)).invert()}updateWorldMatrix(e,t){super.updateWorldMatrix(e,t),this.matrixWorld.decompose(Rd,zd,Bd),Bd.x===1&&Bd.y===1&&Bd.z===1?this.matrixWorldInverse.copy(this.matrixWorld).invert():this.matrixWorldInverse.compose(Rd,zd,Bd.set(1,1,1)).invert()}clone(){return new this.constructor().copy(this)}},Hd=new H,Ud=new V,Wd=new V,Gd=class extends Vd{constructor(e=50,t=1,n=.1,r=2e3){super(),this.isPerspectiveCamera=!0,this.type=`PerspectiveCamera`,this.fov=e,this.zoom=1,this.near=n,this.far=r,this.focus=10,this.aspect=t,this.view=null,this.filmGauge=35,this.filmOffset=0,this.updateProjectionMatrix()}copy(e,t){return super.copy(e,t),this.fov=e.fov,this.zoom=e.zoom,this.near=e.near,this.far=e.far,this.focus=e.focus,this.aspect=e.aspect,this.view=e.view===null?null:Object.assign({},e.view),this.filmGauge=e.filmGauge,this.filmOffset=e.filmOffset,this}setFocalLength(e){let t=.5*this.getFilmHeight()/e;this.fov=bo*2*Math.atan(t),this.updateProjectionMatrix()}getFocalLength(){let e=Math.tan(yo*.5*this.fov);return .5*this.getFilmHeight()/e}getEffectiveFOV(){return bo*2*Math.atan(Math.tan(yo*.5*this.fov)/this.zoom)}getFilmWidth(){return this.filmGauge*Math.min(this.aspect,1)}getFilmHeight(){return this.filmGauge/Math.max(this.aspect,1)}getViewBounds(e,t,n){Hd.set(-1,-1,.5).applyMatrix4(this.projectionMatrixInverse),t.set(Hd.x,Hd.y).multiplyScalar(-e/Hd.z),Hd.set(1,1,.5).applyMatrix4(this.projectionMatrixInverse),n.set(Hd.x,Hd.y).multiplyScalar(-e/Hd.z)}getViewSize(e,t){return this.getViewBounds(e,Ud,Wd),t.subVectors(Wd,Ud)}setViewOffset(e,t,n,r,i,a){this.aspect=e/t,this.view===null&&(this.view={enabled:!0,fullWidth:1,fullHeight:1,offsetX:0,offsetY:0,width:1,height:1}),this.view.enabled=!0,this.view.fullWidth=e,this.view.fullHeight=t,this.view.offsetX=n,this.view.offsetY=r,this.view.width=i,this.view.height=a,this.updateProjectionMatrix()}clearViewOffset(){this.view!==null&&(this.view.enabled=!1),this.updateProjectionMatrix()}updateProjectionMatrix(){let e=this.near,t=e*Math.tan(yo*.5*this.fov)/this.zoom,n=2*t,r=this.aspect*n,i=-.5*r,a=this.view;if(this.view!==null&&this.view.enabled){let e=a.fullWidth,o=a.fullHeight;i+=a.offsetX*r/e,t-=a.offsetY*n/o,r*=a.width/e,n*=a.height/o}let o=this.filmOffset;o!==0&&(i+=e*o/this.getFilmWidth()),this.projectionMatrix.makePerspective(i,i+r,t,t-n,e,this.far,this.coordinateSystem,this.reversedDepth),this.projectionMatrixInverse.copy(this.projectionMatrix).invert()}toJSON(e){let t=super.toJSON(e);return t.object.fov=this.fov,t.object.zoom=this.zoom,t.object.near=this.near,t.object.far=this.far,t.object.focus=this.focus,t.object.aspect=this.aspect,this.view!==null&&(t.object.view=Object.assign({},this.view)),t.object.filmGauge=this.filmGauge,t.object.filmOffset=this.filmOffset,t}},Kd=class extends Vd{constructor(e=-1,t=1,n=1,r=-1,i=.1,a=2e3){super(),this.isOrthographicCamera=!0,this.type=`OrthographicCamera`,this.zoom=1,this.view=null,this.left=e,this.right=t,this.top=n,this.bottom=r,this.near=i,this.far=a,this.updateProjectionMatrix()}copy(e,t){return super.copy(e,t),this.left=e.left,this.right=e.right,this.top=e.top,this.bottom=e.bottom,this.near=e.near,this.far=e.far,this.zoom=e.zoom,this.view=e.view===null?null:Object.assign({},e.view),this}setViewOffset(e,t,n,r,i,a){this.view===null&&(this.view={enabled:!0,fullWidth:1,fullHeight:1,offsetX:0,offsetY:0,width:1,height:1}),this.view.enabled=!0,this.view.fullWidth=e,this.view.fullHeight=t,this.view.offsetX=n,this.view.offsetY=r,this.view.width=i,this.view.height=a,this.updateProjectionMatrix()}clearViewOffset(){this.view!==null&&(this.view.enabled=!1),this.updateProjectionMatrix()}updateProjectionMatrix(){let e=(this.right-this.left)/(2*this.zoom),t=(this.top-this.bottom)/(2*this.zoom),n=(this.right+this.left)/2,r=(this.top+this.bottom)/2,i=n-e,a=n+e,o=r+t,s=r-t;if(this.view!==null&&this.view.enabled){let e=(this.right-this.left)/this.view.fullWidth/this.zoom,t=(this.top-this.bottom)/this.view.fullHeight/this.zoom;i+=e*this.view.offsetX,a=i+e*this.view.width,o-=t*this.view.offsetY,s=o-t*this.view.height}this.projectionMatrix.makeOrthographic(i,a,o,s,this.near,this.far,this.coordinateSystem,this.reversedDepth),this.projectionMatrixInverse.copy(this.projectionMatrix).invert()}toJSON(e){let t=super.toJSON(e);return t.object.zoom=this.zoom,t.object.left=this.left,t.object.right=this.right,t.object.top=this.top,t.object.bottom=this.bottom,t.object.near=this.near,t.object.far=this.far,this.view!==null&&(t.object.view=Object.assign({},this.view)),t}},qd=class extends Ld{constructor(){super(new Kd(-5,5,5,-5,.5,500)),this.isDirectionalLightShadow=!0}},Jd=class extends Md{constructor(e,t){super(e,t),this.isDirectionalLight=!0,this.type=`DirectionalLight`,this.position.copy(zs.DEFAULT_UP),this.updateMatrix(),this.target=new zs,this.shadow=new qd}dispose(){super.dispose(),this.shadow.dispose()}copy(e){return super.copy(e),this.target=e.target.clone(),this.shadow=e.shadow.clone(),this}toJSON(e){let t=super.toJSON(e);return t.object.shadow=this.shadow.toJSON(),t.object.target=this.target.uuid,t}},Yd=-90,Xd=1,Zd=class extends zs{constructor(e,t,n){super(),this.type=`CubeCamera`,this.renderTarget=n,this.coordinateSystem=null,this.activeMipmapLevel=0;let r=new Gd(Yd,Xd,e,t);r.layers=this.layers,this.add(r);let i=new Gd(Yd,Xd,e,t);i.layers=this.layers,this.add(i);let a=new Gd(Yd,Xd,e,t);a.layers=this.layers,this.add(a);let o=new Gd(Yd,Xd,e,t);o.layers=this.layers,this.add(o);let s=new Gd(Yd,Xd,e,t);s.layers=this.layers,this.add(s);let c=new Gd(Yd,Xd,e,t);c.layers=this.layers,this.add(c)}updateCoordinateSystem(){let e=this.coordinateSystem,t=this.children.concat(),[n,r,i,a,o,s]=t;for(let e of t)this.remove(e);if(e===2e3)n.up.set(0,1,0),n.lookAt(1,0,0),r.up.set(0,1,0),r.lookAt(-1,0,0),i.up.set(0,0,-1),i.lookAt(0,1,0),a.up.set(0,0,1),a.lookAt(0,-1,0),o.up.set(0,1,0),o.lookAt(0,0,1),s.up.set(0,1,0),s.lookAt(0,0,-1);else if(e===2001)n.up.set(0,-1,0),n.lookAt(-1,0,0),r.up.set(0,-1,0),r.lookAt(1,0,0),i.up.set(0,0,1),i.lookAt(0,1,0),a.up.set(0,0,-1),a.lookAt(0,-1,0),o.up.set(0,-1,0),o.lookAt(0,0,1),s.up.set(0,-1,0),s.lookAt(0,0,-1);else throw Error(`THREE.CubeCamera.updateCoordinateSystem(): Invalid coordinate system: `+e);for(let e of t)this.add(e),e.updateMatrixWorld()}update(e,t){this.parent===null&&this.updateMatrixWorld();let{renderTarget:n,activeMipmapLevel:r}=this;this.coordinateSystem!==e.coordinateSystem&&(this.coordinateSystem=e.coordinateSystem,this.updateCoordinateSystem());let[i,a,o,s,c,l]=this.children,u=e.getRenderTarget(),d=e.getActiveCubeFace(),f=e.getActiveMipmapLevel(),p=e.xr.enabled;e.xr.enabled=!1;let m=n.texture.generateMipmaps;n.texture.generateMipmaps=!1;let h=!1;h=e.isWebGLRenderer===!0?e.state.buffers.depth.getReversed():e.reversedDepthBuffer,e.setRenderTarget(n,0,r),h&&e.autoClear===!1&&e.clearDepth(),e.render(t,i),e.setRenderTarget(n,1,r),h&&e.autoClear===!1&&e.clearDepth(),e.render(t,a),e.setRenderTarget(n,2,r),h&&e.autoClear===!1&&e.clearDepth(),e.render(t,o),e.setRenderTarget(n,3,r),h&&e.autoClear===!1&&e.clearDepth(),e.render(t,s),e.setRenderTarget(n,4,r),h&&e.autoClear===!1&&e.clearDepth(),e.render(t,c),n.texture.generateMipmaps=m,e.setRenderTarget(n,5,r),h&&e.autoClear===!1&&e.clearDepth(),e.render(t,l),e.setRenderTarget(u,d,f),e.xr.enabled=p,n.texture.needsPMREMUpdate=!0}},Qd=class extends Gd{constructor(e=[]){super(),this.isArrayCamera=!0,this.isMultiViewCamera=!1,this.cameras=e}},$d=class{constructor(){this._previousTime=0,this._currentTime=0,this._startTime=performance.now(),this._delta=0,this._elapsed=0,this._timescale=1,this._document=null,this._pageVisibilityHandler=null}connect(e){this._document=e,e.hidden!==void 0&&(this._pageVisibilityHandler=ef.bind(this),e.addEventListener(`visibilitychange`,this._pageVisibilityHandler,!1))}disconnect(){this._pageVisibilityHandler!==null&&(this._document.removeEventListener(`visibilitychange`,this._pageVisibilityHandler),this._pageVisibilityHandler=null),this._document=null}getDelta(){return this._delta/1e3}getElapsed(){return this._elapsed/1e3}getTimescale(){return this._timescale}setTimescale(e){return this._timescale=e,this}reset(){return this._currentTime=performance.now()-this._startTime,this}dispose(){this.disconnect()}update(e){return this._pageVisibilityHandler!==null&&this._document.hidden===!0?this._delta=0:(this._previousTime=this._currentTime,this._currentTime=(e===void 0?performance.now():e)-this._startTime,this._delta=(this._currentTime-this._previousTime)*this._timescale,this._elapsed+=this._delta),this}};function ef(){this._document.hidden===!1&&this.reset()}var tf=`\\[\\]\\.:\\/`,nf=RegExp(`[\\[\\]\\.:\\/]`,`g`),rf=`[^\\[\\]\\.:\\/]`,af=`[^`+tf.replace(`\\.`,``)+`]`,of=`((?:WC+[\\/:])*)`.replace(`WC`,rf),sf=`(WCOD+)?`.replace(`WCOD`,af),cf=`(?:\\.(WC+)(?:\\[(.+)\\])?)?`.replace(`WC`,rf),lf=`\\.(WC+)(?:\\[(.+)\\])?`.replace(`WC`,rf),uf=RegExp(`^`+of+sf+cf+lf+`$`),df=[`material`,`materials`,`bones`,`map`],ff=class{constructor(e,t,n){let r=n||pf.parseTrackName(t);this._targetGroup=e,this._bindings=e.subscribe_(t,r)}getValue(e,t){this.bind();let n=this._targetGroup.nCachedObjects_,r=this._bindings[n];r!==void 0&&r.getValue(e,t)}setValue(e,t){let n=this._bindings;for(let r=this._targetGroup.nCachedObjects_,i=n.length;r!==i;++r)n[r].setValue(e,t)}bind(){let e=this._bindings;for(let t=this._targetGroup.nCachedObjects_,n=e.length;t!==n;++t)e[t].bind()}unbind(){let e=this._bindings;for(let t=this._targetGroup.nCachedObjects_,n=e.length;t!==n;++t)e[t].unbind()}},pf=class e{constructor(t,n,r){this.path=n,this.parsedPath=r||e.parseTrackName(n),this.node=e.findNode(t,this.parsedPath.nodeName),this.rootNode=t,this.getValue=this._getValue_unbound,this.setValue=this._setValue_unbound}static create(t,n,r){return t&&t.isAnimationObjectGroup?new e.Composite(t,n,r):new e(t,n,r)}static sanitizeNodeName(e){return e.replace(/\s/g,`_`).replace(nf,``)}static parseTrackName(e){let t=uf.exec(e);if(t===null)throw Error(`PropertyBinding: Cannot parse trackName: `+e);let n={nodeName:t[2],objectName:t[3],objectIndex:t[4],propertyName:t[5],propertyIndex:t[6]},r=n.nodeName&&n.nodeName.lastIndexOf(`.`);if(r!==void 0&&r!==-1){let e=n.nodeName.substring(r+1);df.indexOf(e)!==-1&&(n.nodeName=n.nodeName.substring(0,r),n.objectName=e)}if(n.propertyName===null||n.propertyName.length===0)throw Error(`PropertyBinding: can not parse propertyName from trackName: `+e);return n}static findNode(e,t){if(t===void 0||t===``||t===`.`||t===-1||t===e.name||t===e.uuid)return e;if(e.skeleton){let n=e.skeleton.getBoneByName(t);if(n!==void 0)return n}if(e.children){let n=function(e){for(let r=0;r<e.length;r++){let i=e[r];if(i.name===t||i.uuid===t)return i;let a=n(i.children);if(a)return a}return null},r=n(e.children);if(r)return r}return null}_getValue_unavailable(){}_setValue_unavailable(){}_getValue_direct(e,t){e[t]=this.targetObject[this.propertyName]}_getValue_array(e,t){let n=this.resolvedProperty;for(let r=0,i=n.length;r!==i;++r)e[t++]=n[r]}_getValue_arrayElement(e,t){e[t]=this.resolvedProperty[this.propertyIndex]}_getValue_toArray(e,t){this.resolvedProperty.toArray(e,t)}_setValue_direct(e,t){this.targetObject[this.propertyName]=e[t]}_setValue_direct_setNeedsUpdate(e,t){this.targetObject[this.propertyName]=e[t],this.targetObject.needsUpdate=!0}_setValue_direct_setMatrixWorldNeedsUpdate(e,t){this.targetObject[this.propertyName]=e[t],this.targetObject.matrixWorldNeedsUpdate=!0}_setValue_array(e,t){let n=this.resolvedProperty;for(let r=0,i=n.length;r!==i;++r)n[r]=e[t++]}_setValue_array_setNeedsUpdate(e,t){let n=this.resolvedProperty;for(let r=0,i=n.length;r!==i;++r)n[r]=e[t++];this.targetObject.needsUpdate=!0}_setValue_array_setMatrixWorldNeedsUpdate(e,t){let n=this.resolvedProperty;for(let r=0,i=n.length;r!==i;++r)n[r]=e[t++];this.targetObject.matrixWorldNeedsUpdate=!0}_setValue_arrayElement(e,t){this.resolvedProperty[this.propertyIndex]=e[t]}_setValue_arrayElement_setNeedsUpdate(e,t){this.resolvedProperty[this.propertyIndex]=e[t],this.targetObject.needsUpdate=!0}_setValue_arrayElement_setMatrixWorldNeedsUpdate(e,t){this.resolvedProperty[this.propertyIndex]=e[t],this.targetObject.matrixWorldNeedsUpdate=!0}_setValue_fromArray(e,t){this.resolvedProperty.fromArray(e,t)}_setValue_fromArray_setNeedsUpdate(e,t){this.resolvedProperty.fromArray(e,t),this.targetObject.needsUpdate=!0}_setValue_fromArray_setMatrixWorldNeedsUpdate(e,t){this.resolvedProperty.fromArray(e,t),this.targetObject.matrixWorldNeedsUpdate=!0}_getValue_unbound(e,t){this.bind(),this.getValue(e,t)}_setValue_unbound(e,t){this.bind(),this.setValue(e,t)}bind(){let t=this.node,n=this.parsedPath,r=n.objectName,i=n.propertyName,a=n.propertyIndex;if(t||(t=e.findNode(this.rootNode,n.nodeName),this.node=t),this.getValue=this._getValue_unavailable,this.setValue=this._setValue_unavailable,!t){R(`PropertyBinding: No target node found for track: `+this.path+`.`);return}if(r){let e=n.objectIndex;switch(r){case`materials`:if(!t.material){z(`PropertyBinding: Can not bind to material as node does not have a material.`,this);return}if(!t.material.materials){z(`PropertyBinding: Can not bind to material.materials as node.material does not have a materials array.`,this);return}t=t.material.materials;break;case`bones`:if(!t.skeleton){z(`PropertyBinding: Can not bind to bones as node does not have a skeleton.`,this);return}t=t.skeleton.bones;for(let n=0;n<t.length;n++)if(t[n].name===e){e=n;break}break;case`map`:if(`map`in t){t=t.map;break}if(!t.material){z(`PropertyBinding: Can not bind to material as node does not have a material.`,this);return}if(!t.material.map){z(`PropertyBinding: Can not bind to material.map as node.material does not have a map.`,this);return}t=t.material.map;break;default:if(t[r]===void 0){z(`PropertyBinding: Can not bind to objectName of node undefined.`,this);return}t=t[r]}if(e!==void 0){if(t[e]===void 0){z(`PropertyBinding: Trying to bind to objectIndex of objectName, but is undefined.`,this,t);return}t=t[e]}}let o=t[i];if(o===void 0){let e=n.nodeName;z(`PropertyBinding: Trying to update property for track: `+e+`.`+i+` but it wasn't found.`,t);return}let s=this.Versioning.None;this.targetObject=t,t.isMaterial===!0?s=this.Versioning.NeedsUpdate:t.isObject3D===!0&&(s=this.Versioning.MatrixWorldNeedsUpdate);let c=this.BindingType.Direct;if(a!==void 0){if(i===`morphTargetInfluences`){if(!t.geometry){z(`PropertyBinding: Can not bind to morphTargetInfluences because node does not have a geometry.`,this);return}if(!t.geometry.morphAttributes){z(`PropertyBinding: Can not bind to morphTargetInfluences because node does not have a geometry.morphAttributes.`,this);return}t.morphTargetDictionary[a]!==void 0&&(a=t.morphTargetDictionary[a])}c=this.BindingType.ArrayElement,this.resolvedProperty=o,this.propertyIndex=a}else o.fromArray!==void 0&&o.toArray!==void 0?(c=this.BindingType.HasFromToArray,this.resolvedProperty=o):Array.isArray(o)?(c=this.BindingType.EntireArray,this.resolvedProperty=o):this.propertyName=i;this.getValue=this.GetterByBindingType[c],this.setValue=this.SetterByBindingTypeAndVersioning[c][s]}unbind(){this.node=null,this.getValue=this._getValue_unbound,this.setValue=this._setValue_unbound}};pf.Composite=ff,pf.prototype.BindingType={Direct:0,EntireArray:1,ArrayElement:2,HasFromToArray:3},pf.prototype.Versioning={None:0,NeedsUpdate:1,MatrixWorldNeedsUpdate:2},pf.prototype.GetterByBindingType=[pf.prototype._getValue_direct,pf.prototype._getValue_array,pf.prototype._getValue_arrayElement,pf.prototype._getValue_toArray],pf.prototype.SetterByBindingTypeAndVersioning=[[pf.prototype._setValue_direct,pf.prototype._setValue_direct_setNeedsUpdate,pf.prototype._setValue_direct_setMatrixWorldNeedsUpdate],[pf.prototype._setValue_array,pf.prototype._setValue_array_setNeedsUpdate,pf.prototype._setValue_array_setMatrixWorldNeedsUpdate],[pf.prototype._setValue_arrayElement,pf.prototype._setValue_arrayElement_setNeedsUpdate,pf.prototype._setValue_arrayElement_setMatrixWorldNeedsUpdate],[pf.prototype._setValue_fromArray,pf.prototype._setValue_fromArray_setNeedsUpdate,pf.prototype._setValue_fromArray_setMatrixWorldNeedsUpdate]];var mf=new fs,hf=class{constructor(e,t,n=0,r=1/0){this.ray=new gl(e,t),this.near=n,this.far=r,this.camera=null,this.layers=new Cs,this.params={Mesh:{},Line:{threshold:1},LOD:{},Points:{threshold:1},Sprite:{}}}set(e,t){this.ray.set(e,t)}setFromCamera(e,t){t.isPerspectiveCamera?(this.ray.origin.setFromMatrixPosition(t.matrixWorld),this.ray.direction.set(e.x,e.y,.5).unproject(t).sub(this.ray.origin).normalize(),this.camera=t):t.isOrthographicCamera?(this.ray.origin.set(e.x,e.y,(t.near+t.far)/(t.near-t.far)).unproject(t),this.ray.direction.set(0,0,-1).transformDirection(t.matrixWorld),this.camera=t):z(`Raycaster: Unsupported camera type: `+t.type)}setFromXRController(e){return mf.identity().extractRotation(e.matrixWorld),this.ray.origin.setFromMatrixPosition(e.matrixWorld),this.ray.direction.set(0,0,-1).applyMatrix4(mf),this}intersectObject(e,t=!0,n=[]){return _f(e,this,n,t),n.sort(gf),n}intersectObjects(e,t=!0,n=[]){for(let r=0,i=e.length;r<i;r++)_f(e[r],this,n,t);return n.sort(gf),n}};function gf(e,t){return e.distance-t.distance}function _f(e,t,n,r){let i=!0;if(e.layers.test(t.layers)&&e.raycast(t,n)===!1&&(i=!1),i===!0&&r===!0){let r=e.children;for(let e=0,i=r.length;e<i;e++)_f(r[e],t,n,!0)}}var vf=class{constructor(e=1,t=0,n=0){this.radius=e,this.phi=t,this.theta=n}set(e,t,n){return this.radius=e,this.phi=t,this.theta=n,this}copy(e){return this.radius=e.radius,this.phi=e.phi,this.theta=e.theta,this}makeSafe(){let e=1e-6;return this.phi=B(this.phi,e,Math.PI-e),this}setFromVector3(e){return this.setFromCartesianCoords(e.x,e.y,e.z)}setFromCartesianCoords(e,t,n){return this.radius=Math.sqrt(e*e+t*t+n*n),this.radius===0?(this.theta=0,this.phi=0):(this.theta=Math.atan2(e,n),this.phi=Math.acos(B(t/this.radius,-1,1))),this}clone(){return new this.constructor().copy(this)}};(class e{static{e.prototype.isMatrix2=!0}constructor(e,t,n,r){this.elements=[1,0,0,1],e!==void 0&&this.set(e,t,n,r)}identity(){return this.set(1,0,0,1),this}fromArray(e,t=0){for(let n=0;n<4;n++)this.elements[n]=e[n+t];return this}set(e,t,n,r){let i=this.elements;return i[0]=e,i[2]=t,i[1]=n,i[3]=r,this}});var yf=class extends cu{constructor(e=10,t=10,n=4473924,r=8947848){n=new W(n),r=new W(r);let i=t/2,a=e/t,o=e/2,s=[],c=[];for(let e=0,l=0,u=-o;e<=t;e++,u+=a){s.push(-o,0,u,o,0,u),s.push(u,0,-o,u,0,o);let t=e===i?n:r;t.toArray(c,l),l+=3,t.toArray(c,l),l+=3,t.toArray(c,l),l+=3,t.toArray(c,l),l+=3}let l=new Vc;l.setAttribute(`position`,new G(s,3)),l.setAttribute(`color`,new G(c,3));let u=new Xl({vertexColors:!0,toneMapped:!1});super(l,u),this.type=`GridHelper`}dispose(){this.geometry.dispose(),this.material.dispose()}},bf=new lc,xf=class extends cu{constructor(e,t=16776960){let n=new Uint16Array([0,1,1,2,2,3,3,0,4,5,5,6,6,7,7,4,0,4,1,5,2,6,3,7]),r=new Float32Array(24),i=new Vc;i.setIndex(new Dc(n,1)),i.setAttribute(`position`,new Dc(r,3)),super(i,new Xl({color:t,toneMapped:!1})),this.object=e,this.type=`BoxHelper`,this.matrixAutoUpdate=!1,this.update()}update(){if(this.object!==void 0&&bf.setFromObject(this.object),bf.isEmpty())return;let e=bf.min,t=bf.max,n=this.geometry.attributes.position,r=n.array;r[0]=t.x,r[1]=t.y,r[2]=t.z,r[3]=e.x,r[4]=t.y,r[5]=t.z,r[6]=e.x,r[7]=e.y,r[8]=t.z,r[9]=t.x,r[10]=e.y,r[11]=t.z,r[12]=t.x,r[13]=t.y,r[14]=e.z,r[15]=e.x,r[16]=t.y,r[17]=e.z,r[18]=e.x,r[19]=e.y,r[20]=e.z,r[21]=t.x,r[22]=e.y,r[23]=e.z,n.needsUpdate=!0,this.geometry.computeBoundingSphere()}setFromObject(e){return this.object=e,this.update(),this}copy(e,t){return super.copy(e,t),this.object=e.object,this}dispose(){this.geometry.dispose(),this.material.dispose()}},Sf=new H,Cf,wf,Tf=class extends zs{constructor(e=new H(0,0,1),t=new H(0,0,0),n=1,r=16776960,i=n*.2,a=i*.2){super(),this.type=`ArrowHelper`,Cf===void 0&&(Cf=new Vc,Cf.setAttribute(`position`,new G([0,0,0,0,1,0],3)),wf=new gu(.5,1,5,1),wf.translate(0,-.5,0)),this.position.copy(t),this.line=new iu(Cf,new Xl({color:r,toneMapped:!1})),this.line.matrixAutoUpdate=!1,this.add(this.line),this.cone=new kl(wf,new _l({color:r,toneMapped:!1})),this.cone.matrixAutoUpdate=!1,this.add(this.cone),this.setDirection(e),this.setLength(n,i,a)}setDirection(e){if(e.y>.99999)this.quaternion.set(0,0,0,1);else if(e.y<-.99999)this.quaternion.set(1,0,0,0);else{Sf.set(e.z,0,-e.x).normalize();let t=Math.acos(e.y);this.quaternion.setFromAxisAngle(Sf,t)}}setLength(e,t=e*.2,n=t*.2){this.line.scale.set(1,Math.max(1e-4,e-t),1),this.line.updateMatrix(),this.cone.scale.set(n,t,n),this.cone.position.y=e,this.cone.updateMatrix()}setColor(e){this.line.material.color.set(e),this.cone.material.color.set(e)}copy(e){return super.copy(e,!1),this.line.copy(e.line),this.cone.copy(e.cone),this}dispose(){this.line.geometry.dispose(),this.line.material.dispose(),this.cone.geometry.dispose(),this.cone.material.dispose()}},Ef=class extends go{constructor(e,t=null){super(),this.object=e,this.domElement=t,this.enabled=!0,this.state=-1,this.keys={},this.mouseButtons={LEFT:null,MIDDLE:null,RIGHT:null},this.touches={ONE:null,TWO:null}}connect(e){if(e===void 0){R(`Controls: connect() now requires an element.`);return}this.domElement!==null&&this.disconnect(),this.domElement=e}disconnect(){}dispose(){}update(){}};function Df(e,t,n,r){let i=Of(r);switch(n){case Xi:return e*t;case ta:return e*t/i.components*i.byteLength;case na:return e*t/i.components*i.byteLength;case ra:return e*t*2/i.components*i.byteLength;case ia:return e*t*2/i.components*i.byteLength;case Zi:return e*t*3/i.components*i.byteLength;case Qi:return e*t*4/i.components*i.byteLength;case aa:return e*t*4/i.components*i.byteLength;case oa:case sa:return Math.floor((e+3)/4)*Math.floor((t+3)/4)*8;case ca:case la:return Math.floor((e+3)/4)*Math.floor((t+3)/4)*16;case da:case pa:return Math.max(e,16)*Math.max(t,8)/4;case ua:case fa:return Math.max(e,8)*Math.max(t,8)/2;case ma:case ha:case _a:case va:return Math.floor((e+3)/4)*Math.floor((t+3)/4)*8;case ga:case ya:case ba:return Math.floor((e+3)/4)*Math.floor((t+3)/4)*16;case xa:return Math.floor((e+3)/4)*Math.floor((t+3)/4)*16;case Sa:return Math.floor((e+4)/5)*Math.floor((t+3)/4)*16;case Ca:return Math.floor((e+4)/5)*Math.floor((t+4)/5)*16;case wa:return Math.floor((e+5)/6)*Math.floor((t+4)/5)*16;case Ta:return Math.floor((e+5)/6)*Math.floor((t+5)/6)*16;case Ea:return Math.floor((e+7)/8)*Math.floor((t+4)/5)*16;case Da:return Math.floor((e+7)/8)*Math.floor((t+5)/6)*16;case Oa:return Math.floor((e+7)/8)*Math.floor((t+7)/8)*16;case ka:return Math.floor((e+9)/10)*Math.floor((t+4)/5)*16;case Aa:return Math.floor((e+9)/10)*Math.floor((t+5)/6)*16;case ja:return Math.floor((e+9)/10)*Math.floor((t+7)/8)*16;case Ma:return Math.floor((e+9)/10)*Math.floor((t+9)/10)*16;case Na:return Math.floor((e+11)/12)*Math.floor((t+9)/10)*16;case Pa:return Math.floor((e+11)/12)*Math.floor((t+11)/12)*16;case Fa:case Ia:case La:return Math.ceil(e/4)*Math.ceil(t/4)*16;case Ra:case za:return Math.ceil(e/4)*Math.ceil(t/4)*8;case Ba:case Va:return Math.ceil(e/4)*Math.ceil(t/4)*16}throw Error(`Unable to determine texture byte length for ${n} format.`)}function Of(e){switch(e){case Li:case Ri:return{byteLength:1,components:1};case Bi:case zi:case Wi:return{byteLength:2,components:1};case Gi:case Ki:return{byteLength:2,components:4};case Hi:case Vi:case Ui:return{byteLength:4,components:1};case Ji:case Yi:return{byteLength:4,components:3}}throw Error(`Unknown texture type ${e}.`)}typeof __THREE_DEVTOOLS__<`u`&&__THREE_DEVTOOLS__.dispatchEvent(new CustomEvent(`register`,{detail:{revision:`184`}})),typeof window<`u`&&(window.__THREE__?R(`WARNING: Multiple instances of Three.js being imported.`):window.__THREE__=`184`);function kf(){let e=null,t=!1,n=null,r=null;function i(t,a){n(t,a),r=e.requestAnimationFrame(i)}return{start:function(){t!==!0&&n!==null&&e!==null&&(r=e.requestAnimationFrame(i),t=!0)},stop:function(){e!==null&&e.cancelAnimationFrame(r),t=!1},setAnimationLoop:function(e){n=e},setContext:function(t){e=t}}}function Af(e){let t=new WeakMap;function n(t,n){let r=t.array,i=t.usage,a=r.byteLength,o=e.createBuffer();e.bindBuffer(n,o),e.bufferData(n,r,i),t.onUploadCallback();let s;if(r instanceof Float32Array)s=e.FLOAT;else if(typeof Float16Array<`u`&&r instanceof Float16Array)s=e.HALF_FLOAT;else if(r instanceof Uint16Array)s=t.isFloat16BufferAttribute?e.HALF_FLOAT:e.UNSIGNED_SHORT;else if(r instanceof Int16Array)s=e.SHORT;else if(r instanceof Uint32Array)s=e.UNSIGNED_INT;else if(r instanceof Int32Array)s=e.INT;else if(r instanceof Int8Array)s=e.BYTE;else if(r instanceof Uint8Array)s=e.UNSIGNED_BYTE;else if(r instanceof Uint8ClampedArray)s=e.UNSIGNED_BYTE;else throw Error(`THREE.WebGLAttributes: Unsupported buffer data format: `+r);return{buffer:o,type:s,bytesPerElement:r.BYTES_PER_ELEMENT,version:t.version,size:a}}function r(t,n,r){let i=n.array,a=n.updateRanges;if(e.bindBuffer(r,t),a.length===0)e.bufferSubData(r,0,i);else{a.sort((e,t)=>e.start-t.start);let t=0;for(let e=1;e<a.length;e++){let n=a[t],r=a[e];r.start<=n.start+n.count+1?n.count=Math.max(n.count,r.start+r.count-n.start):(++t,a[t]=r)}a.length=t+1;for(let t=0,n=a.length;t<n;t++){let n=a[t];e.bufferSubData(r,n.start*i.BYTES_PER_ELEMENT,i,n.start,n.count)}n.clearUpdateRanges()}n.onUploadCallback()}function i(e){return e.isInterleavedBufferAttribute&&(e=e.data),t.get(e)}function a(n){n.isInterleavedBufferAttribute&&(n=n.data);let r=t.get(n);r&&(e.deleteBuffer(r.buffer),t.delete(n))}function o(e,i){if(e.isInterleavedBufferAttribute&&(e=e.data),e.isGLBufferAttribute){let n=t.get(e);(!n||n.version<e.version)&&t.set(e,{buffer:e.buffer,type:e.type,bytesPerElement:e.elementSize,version:e.version});return}let a=t.get(e);if(a===void 0)t.set(e,n(e,i));else if(a.version<e.version){if(a.size!==e.array.byteLength)throw Error(`THREE.WebGLAttributes: The size of the buffer attribute's array buffer does not match the original size. Resizing buffer attributes is not supported.`);r(a.buffer,e,i),a.version=e.version}}return{get:i,remove:a,update:o}}var K={alphahash_fragment:`#ifdef USE_ALPHAHASH
	if ( diffuseColor.a < getAlphaHashThreshold( vPosition ) ) discard;
#endif`,alphahash_pars_fragment:`#ifdef USE_ALPHAHASH
	const float ALPHA_HASH_SCALE = 0.05;
	float hash2D( vec2 value ) {
		return fract( 1.0e4 * sin( 17.0 * value.x + 0.1 * value.y ) * ( 0.1 + abs( sin( 13.0 * value.y + value.x ) ) ) );
	}
	float hash3D( vec3 value ) {
		return hash2D( vec2( hash2D( value.xy ), value.z ) );
	}
	float getAlphaHashThreshold( vec3 position ) {
		float maxDeriv = max(
			length( dFdx( position.xyz ) ),
			length( dFdy( position.xyz ) )
		);
		float pixScale = 1.0 / ( ALPHA_HASH_SCALE * maxDeriv );
		vec2 pixScales = vec2(
			exp2( floor( log2( pixScale ) ) ),
			exp2( ceil( log2( pixScale ) ) )
		);
		vec2 alpha = vec2(
			hash3D( floor( pixScales.x * position.xyz ) ),
			hash3D( floor( pixScales.y * position.xyz ) )
		);
		float lerpFactor = fract( log2( pixScale ) );
		float x = ( 1.0 - lerpFactor ) * alpha.x + lerpFactor * alpha.y;
		float a = min( lerpFactor, 1.0 - lerpFactor );
		vec3 cases = vec3(
			x * x / ( 2.0 * a * ( 1.0 - a ) ),
			( x - 0.5 * a ) / ( 1.0 - a ),
			1.0 - ( ( 1.0 - x ) * ( 1.0 - x ) / ( 2.0 * a * ( 1.0 - a ) ) )
		);
		float threshold = ( x < ( 1.0 - a ) )
			? ( ( x < a ) ? cases.x : cases.y )
			: cases.z;
		return clamp( threshold , 1.0e-6, 1.0 );
	}
#endif`,alphamap_fragment:`#ifdef USE_ALPHAMAP
	diffuseColor.a *= texture2D( alphaMap, vAlphaMapUv ).g;
#endif`,alphamap_pars_fragment:`#ifdef USE_ALPHAMAP
	uniform sampler2D alphaMap;
#endif`,alphatest_fragment:`#ifdef USE_ALPHATEST
	#ifdef ALPHA_TO_COVERAGE
	diffuseColor.a = smoothstep( alphaTest, alphaTest + fwidth( diffuseColor.a ), diffuseColor.a );
	if ( diffuseColor.a == 0.0 ) discard;
	#else
	if ( diffuseColor.a < alphaTest ) discard;
	#endif
#endif`,alphatest_pars_fragment:`#ifdef USE_ALPHATEST
	uniform float alphaTest;
#endif`,aomap_fragment:`#ifdef USE_AOMAP
	float ambientOcclusion = ( texture2D( aoMap, vAoMapUv ).r - 1.0 ) * aoMapIntensity + 1.0;
	reflectedLight.indirectDiffuse *= ambientOcclusion;
	#if defined( USE_CLEARCOAT ) 
		clearcoatSpecularIndirect *= ambientOcclusion;
	#endif
	#if defined( USE_SHEEN ) 
		sheenSpecularIndirect *= ambientOcclusion;
	#endif
	#if defined( USE_ENVMAP ) && defined( STANDARD )
		float dotNV = saturate( dot( geometryNormal, geometryViewDir ) );
		reflectedLight.indirectSpecular *= computeSpecularOcclusion( dotNV, ambientOcclusion, material.roughness );
	#endif
#endif`,aomap_pars_fragment:`#ifdef USE_AOMAP
	uniform sampler2D aoMap;
	uniform float aoMapIntensity;
#endif`,batching_pars_vertex:`#ifdef USE_BATCHING
	#if ! defined( GL_ANGLE_multi_draw )
	#define gl_DrawID _gl_DrawID
	uniform int _gl_DrawID;
	#endif
	uniform highp sampler2D batchingTexture;
	uniform highp usampler2D batchingIdTexture;
	mat4 getBatchingMatrix( const in float i ) {
		int size = textureSize( batchingTexture, 0 ).x;
		int j = int( i ) * 4;
		int x = j % size;
		int y = j / size;
		vec4 v1 = texelFetch( batchingTexture, ivec2( x, y ), 0 );
		vec4 v2 = texelFetch( batchingTexture, ivec2( x + 1, y ), 0 );
		vec4 v3 = texelFetch( batchingTexture, ivec2( x + 2, y ), 0 );
		vec4 v4 = texelFetch( batchingTexture, ivec2( x + 3, y ), 0 );
		return mat4( v1, v2, v3, v4 );
	}
	float getIndirectIndex( const in int i ) {
		int size = textureSize( batchingIdTexture, 0 ).x;
		int x = i % size;
		int y = i / size;
		return float( texelFetch( batchingIdTexture, ivec2( x, y ), 0 ).r );
	}
#endif
#ifdef USE_BATCHING_COLOR
	uniform sampler2D batchingColorTexture;
	vec4 getBatchingColor( const in float i ) {
		int size = textureSize( batchingColorTexture, 0 ).x;
		int j = int( i );
		int x = j % size;
		int y = j / size;
		return texelFetch( batchingColorTexture, ivec2( x, y ), 0 );
	}
#endif`,batching_vertex:`#ifdef USE_BATCHING
	mat4 batchingMatrix = getBatchingMatrix( getIndirectIndex( gl_DrawID ) );
#endif`,begin_vertex:`vec3 transformed = vec3( position );
#ifdef USE_ALPHAHASH
	vPosition = vec3( position );
#endif`,beginnormal_vertex:`vec3 objectNormal = vec3( normal );
#ifdef USE_TANGENT
	vec3 objectTangent = vec3( tangent.xyz );
#endif`,bsdfs:`float G_BlinnPhong_Implicit( ) {
	return 0.25;
}
float D_BlinnPhong( const in float shininess, const in float dotNH ) {
	return RECIPROCAL_PI * ( shininess * 0.5 + 1.0 ) * pow( dotNH, shininess );
}
vec3 BRDF_BlinnPhong( const in vec3 lightDir, const in vec3 viewDir, const in vec3 normal, const in vec3 specularColor, const in float shininess ) {
	vec3 halfDir = normalize( lightDir + viewDir );
	float dotNH = saturate( dot( normal, halfDir ) );
	float dotVH = saturate( dot( viewDir, halfDir ) );
	vec3 F = F_Schlick( specularColor, 1.0, dotVH );
	float G = G_BlinnPhong_Implicit( );
	float D = D_BlinnPhong( shininess, dotNH );
	return F * ( G * D );
} // validated`,iridescence_fragment:`#ifdef USE_IRIDESCENCE
	const mat3 XYZ_TO_REC709 = mat3(
		 3.2404542, -0.9692660,  0.0556434,
		-1.5371385,  1.8760108, -0.2040259,
		-0.4985314,  0.0415560,  1.0572252
	);
	vec3 Fresnel0ToIor( vec3 fresnel0 ) {
		vec3 sqrtF0 = sqrt( fresnel0 );
		return ( vec3( 1.0 ) + sqrtF0 ) / ( vec3( 1.0 ) - sqrtF0 );
	}
	vec3 IorToFresnel0( vec3 transmittedIor, float incidentIor ) {
		return pow2( ( transmittedIor - vec3( incidentIor ) ) / ( transmittedIor + vec3( incidentIor ) ) );
	}
	float IorToFresnel0( float transmittedIor, float incidentIor ) {
		return pow2( ( transmittedIor - incidentIor ) / ( transmittedIor + incidentIor ));
	}
	vec3 evalSensitivity( float OPD, vec3 shift ) {
		float phase = 2.0 * PI * OPD * 1.0e-9;
		vec3 val = vec3( 5.4856e-13, 4.4201e-13, 5.2481e-13 );
		vec3 pos = vec3( 1.6810e+06, 1.7953e+06, 2.2084e+06 );
		vec3 var = vec3( 4.3278e+09, 9.3046e+09, 6.6121e+09 );
		vec3 xyz = val * sqrt( 2.0 * PI * var ) * cos( pos * phase + shift ) * exp( - pow2( phase ) * var );
		xyz.x += 9.7470e-14 * sqrt( 2.0 * PI * 4.5282e+09 ) * cos( 2.2399e+06 * phase + shift[ 0 ] ) * exp( - 4.5282e+09 * pow2( phase ) );
		xyz /= 1.0685e-7;
		vec3 rgb = XYZ_TO_REC709 * xyz;
		return rgb;
	}
	vec3 evalIridescence( float outsideIOR, float eta2, float cosTheta1, float thinFilmThickness, vec3 baseF0 ) {
		vec3 I;
		float iridescenceIOR = mix( outsideIOR, eta2, smoothstep( 0.0, 0.03, thinFilmThickness ) );
		float sinTheta2Sq = pow2( outsideIOR / iridescenceIOR ) * ( 1.0 - pow2( cosTheta1 ) );
		float cosTheta2Sq = 1.0 - sinTheta2Sq;
		if ( cosTheta2Sq < 0.0 ) {
			return vec3( 1.0 );
		}
		float cosTheta2 = sqrt( cosTheta2Sq );
		float R0 = IorToFresnel0( iridescenceIOR, outsideIOR );
		float R12 = F_Schlick( R0, 1.0, cosTheta1 );
		float T121 = 1.0 - R12;
		float phi12 = 0.0;
		if ( iridescenceIOR < outsideIOR ) phi12 = PI;
		float phi21 = PI - phi12;
		vec3 baseIOR = Fresnel0ToIor( clamp( baseF0, 0.0, 0.9999 ) );		vec3 R1 = IorToFresnel0( baseIOR, iridescenceIOR );
		vec3 R23 = F_Schlick( R1, 1.0, cosTheta2 );
		vec3 phi23 = vec3( 0.0 );
		if ( baseIOR[ 0 ] < iridescenceIOR ) phi23[ 0 ] = PI;
		if ( baseIOR[ 1 ] < iridescenceIOR ) phi23[ 1 ] = PI;
		if ( baseIOR[ 2 ] < iridescenceIOR ) phi23[ 2 ] = PI;
		float OPD = 2.0 * iridescenceIOR * thinFilmThickness * cosTheta2;
		vec3 phi = vec3( phi21 ) + phi23;
		vec3 R123 = clamp( R12 * R23, 1e-5, 0.9999 );
		vec3 r123 = sqrt( R123 );
		vec3 Rs = pow2( T121 ) * R23 / ( vec3( 1.0 ) - R123 );
		vec3 C0 = R12 + Rs;
		I = C0;
		vec3 Cm = Rs - T121;
		for ( int m = 1; m <= 2; ++ m ) {
			Cm *= r123;
			vec3 Sm = 2.0 * evalSensitivity( float( m ) * OPD, float( m ) * phi );
			I += Cm * Sm;
		}
		return max( I, vec3( 0.0 ) );
	}
#endif`,bumpmap_pars_fragment:`#ifdef USE_BUMPMAP
	uniform sampler2D bumpMap;
	uniform float bumpScale;
	vec2 dHdxy_fwd() {
		vec2 dSTdx = dFdx( vBumpMapUv );
		vec2 dSTdy = dFdy( vBumpMapUv );
		float Hll = bumpScale * texture2D( bumpMap, vBumpMapUv ).x;
		float dBx = bumpScale * texture2D( bumpMap, vBumpMapUv + dSTdx ).x - Hll;
		float dBy = bumpScale * texture2D( bumpMap, vBumpMapUv + dSTdy ).x - Hll;
		return vec2( dBx, dBy );
	}
	vec3 perturbNormalArb( vec3 surf_pos, vec3 surf_norm, vec2 dHdxy, float faceDirection ) {
		vec3 vSigmaX = normalize( dFdx( surf_pos.xyz ) );
		vec3 vSigmaY = normalize( dFdy( surf_pos.xyz ) );
		vec3 vN = surf_norm;
		vec3 R1 = cross( vSigmaY, vN );
		vec3 R2 = cross( vN, vSigmaX );
		float fDet = dot( vSigmaX, R1 ) * faceDirection;
		vec3 vGrad = sign( fDet ) * ( dHdxy.x * R1 + dHdxy.y * R2 );
		return normalize( abs( fDet ) * surf_norm - vGrad );
	}
#endif`,clipping_planes_fragment:`#if NUM_CLIPPING_PLANES > 0
	vec4 plane;
	#ifdef ALPHA_TO_COVERAGE
		float distanceToPlane, distanceGradient;
		float clipOpacity = 1.0;
		#pragma unroll_loop_start
		for ( int i = 0; i < UNION_CLIPPING_PLANES; i ++ ) {
			plane = clippingPlanes[ i ];
			distanceToPlane = - dot( vClipPosition, plane.xyz ) + plane.w;
			distanceGradient = fwidth( distanceToPlane ) / 2.0;
			clipOpacity *= smoothstep( - distanceGradient, distanceGradient, distanceToPlane );
			if ( clipOpacity == 0.0 ) discard;
		}
		#pragma unroll_loop_end
		#if UNION_CLIPPING_PLANES < NUM_CLIPPING_PLANES
			float unionClipOpacity = 1.0;
			#pragma unroll_loop_start
			for ( int i = UNION_CLIPPING_PLANES; i < NUM_CLIPPING_PLANES; i ++ ) {
				plane = clippingPlanes[ i ];
				distanceToPlane = - dot( vClipPosition, plane.xyz ) + plane.w;
				distanceGradient = fwidth( distanceToPlane ) / 2.0;
				unionClipOpacity *= 1.0 - smoothstep( - distanceGradient, distanceGradient, distanceToPlane );
			}
			#pragma unroll_loop_end
			clipOpacity *= 1.0 - unionClipOpacity;
		#endif
		diffuseColor.a *= clipOpacity;
		if ( diffuseColor.a == 0.0 ) discard;
	#else
		#pragma unroll_loop_start
		for ( int i = 0; i < UNION_CLIPPING_PLANES; i ++ ) {
			plane = clippingPlanes[ i ];
			if ( dot( vClipPosition, plane.xyz ) > plane.w ) discard;
		}
		#pragma unroll_loop_end
		#if UNION_CLIPPING_PLANES < NUM_CLIPPING_PLANES
			bool clipped = true;
			#pragma unroll_loop_start
			for ( int i = UNION_CLIPPING_PLANES; i < NUM_CLIPPING_PLANES; i ++ ) {
				plane = clippingPlanes[ i ];
				clipped = ( dot( vClipPosition, plane.xyz ) > plane.w ) && clipped;
			}
			#pragma unroll_loop_end
			if ( clipped ) discard;
		#endif
	#endif
#endif`,clipping_planes_pars_fragment:`#if NUM_CLIPPING_PLANES > 0
	varying vec3 vClipPosition;
	uniform vec4 clippingPlanes[ NUM_CLIPPING_PLANES ];
#endif`,clipping_planes_pars_vertex:`#if NUM_CLIPPING_PLANES > 0
	varying vec3 vClipPosition;
#endif`,clipping_planes_vertex:`#if NUM_CLIPPING_PLANES > 0
	vClipPosition = - mvPosition.xyz;
#endif`,color_fragment:`#if defined( USE_COLOR ) || defined( USE_COLOR_ALPHA )
	diffuseColor *= vColor;
#endif`,color_pars_fragment:`#if defined( USE_COLOR ) || defined( USE_COLOR_ALPHA )
	varying vec4 vColor;
#endif`,color_pars_vertex:`#if defined( USE_COLOR ) || defined( USE_COLOR_ALPHA ) || defined( USE_INSTANCING_COLOR ) || defined( USE_BATCHING_COLOR )
	varying vec4 vColor;
#endif`,color_vertex:`#if defined( USE_COLOR ) || defined( USE_COLOR_ALPHA ) || defined( USE_INSTANCING_COLOR ) || defined( USE_BATCHING_COLOR )
	vColor = vec4( 1.0 );
#endif
#ifdef USE_COLOR_ALPHA
	vColor *= color;
#elif defined( USE_COLOR )
	vColor.rgb *= color;
#endif
#ifdef USE_INSTANCING_COLOR
	vColor.rgb *= instanceColor.rgb;
#endif
#ifdef USE_BATCHING_COLOR
	vColor *= getBatchingColor( getIndirectIndex( gl_DrawID ) );
#endif`,common:`#define PI 3.141592653589793
#define PI2 6.283185307179586
#define PI_HALF 1.5707963267948966
#define RECIPROCAL_PI 0.3183098861837907
#define RECIPROCAL_PI2 0.15915494309189535
#define EPSILON 1e-6
#ifndef saturate
#define saturate( a ) clamp( a, 0.0, 1.0 )
#endif
#define whiteComplement( a ) ( 1.0 - saturate( a ) )
float pow2( const in float x ) { return x*x; }
vec3 pow2( const in vec3 x ) { return x*x; }
float pow3( const in float x ) { return x*x*x; }
float pow4( const in float x ) { float x2 = x*x; return x2*x2; }
float max3( const in vec3 v ) { return max( max( v.x, v.y ), v.z ); }
float average( const in vec3 v ) { return dot( v, vec3( 0.3333333 ) ); }
highp float rand( const in vec2 uv ) {
	const highp float a = 12.9898, b = 78.233, c = 43758.5453;
	highp float dt = dot( uv.xy, vec2( a,b ) ), sn = mod( dt, PI );
	return fract( sin( sn ) * c );
}
#ifdef HIGH_PRECISION
	float precisionSafeLength( vec3 v ) { return length( v ); }
#else
	float precisionSafeLength( vec3 v ) {
		float maxComponent = max3( abs( v ) );
		return length( v / maxComponent ) * maxComponent;
	}
#endif
struct IncidentLight {
	vec3 color;
	vec3 direction;
	bool visible;
};
struct ReflectedLight {
	vec3 directDiffuse;
	vec3 directSpecular;
	vec3 indirectDiffuse;
	vec3 indirectSpecular;
};
#ifdef USE_ALPHAHASH
	varying vec3 vPosition;
#endif
vec3 transformDirection( in vec3 dir, in mat4 matrix ) {
	return normalize( ( matrix * vec4( dir, 0.0 ) ).xyz );
}
vec3 inverseTransformDirection( in vec3 dir, in mat4 matrix ) {
	return normalize( ( vec4( dir, 0.0 ) * matrix ).xyz );
}
bool isPerspectiveMatrix( mat4 m ) {
	return m[ 2 ][ 3 ] == - 1.0;
}
vec2 equirectUv( in vec3 dir ) {
	float u = atan( dir.z, dir.x ) * RECIPROCAL_PI2 + 0.5;
	float v = asin( clamp( dir.y, - 1.0, 1.0 ) ) * RECIPROCAL_PI + 0.5;
	return vec2( u, v );
}
vec3 BRDF_Lambert( const in vec3 diffuseColor ) {
	return RECIPROCAL_PI * diffuseColor;
}
vec3 F_Schlick( const in vec3 f0, const in float f90, const in float dotVH ) {
	float fresnel = exp2( ( - 5.55473 * dotVH - 6.98316 ) * dotVH );
	return f0 * ( 1.0 - fresnel ) + ( f90 * fresnel );
}
float F_Schlick( const in float f0, const in float f90, const in float dotVH ) {
	float fresnel = exp2( ( - 5.55473 * dotVH - 6.98316 ) * dotVH );
	return f0 * ( 1.0 - fresnel ) + ( f90 * fresnel );
} // validated`,cube_uv_reflection_fragment:`#ifdef ENVMAP_TYPE_CUBE_UV
	#define cubeUV_minMipLevel 4.0
	#define cubeUV_minTileSize 16.0
	float getFace( vec3 direction ) {
		vec3 absDirection = abs( direction );
		float face = - 1.0;
		if ( absDirection.x > absDirection.z ) {
			if ( absDirection.x > absDirection.y )
				face = direction.x > 0.0 ? 0.0 : 3.0;
			else
				face = direction.y > 0.0 ? 1.0 : 4.0;
		} else {
			if ( absDirection.z > absDirection.y )
				face = direction.z > 0.0 ? 2.0 : 5.0;
			else
				face = direction.y > 0.0 ? 1.0 : 4.0;
		}
		return face;
	}
	vec2 getUV( vec3 direction, float face ) {
		vec2 uv;
		if ( face == 0.0 ) {
			uv = vec2( direction.z, direction.y ) / abs( direction.x );
		} else if ( face == 1.0 ) {
			uv = vec2( - direction.x, - direction.z ) / abs( direction.y );
		} else if ( face == 2.0 ) {
			uv = vec2( - direction.x, direction.y ) / abs( direction.z );
		} else if ( face == 3.0 ) {
			uv = vec2( - direction.z, direction.y ) / abs( direction.x );
		} else if ( face == 4.0 ) {
			uv = vec2( - direction.x, direction.z ) / abs( direction.y );
		} else {
			uv = vec2( direction.x, direction.y ) / abs( direction.z );
		}
		return 0.5 * ( uv + 1.0 );
	}
	vec3 bilinearCubeUV( sampler2D envMap, vec3 direction, float mipInt ) {
		float face = getFace( direction );
		float filterInt = max( cubeUV_minMipLevel - mipInt, 0.0 );
		mipInt = max( mipInt, cubeUV_minMipLevel );
		float faceSize = exp2( mipInt );
		highp vec2 uv = getUV( direction, face ) * ( faceSize - 2.0 ) + 1.0;
		if ( face > 2.0 ) {
			uv.y += faceSize;
			face -= 3.0;
		}
		uv.x += face * faceSize;
		uv.x += filterInt * 3.0 * cubeUV_minTileSize;
		uv.y += 4.0 * ( exp2( CUBEUV_MAX_MIP ) - faceSize );
		uv.x *= CUBEUV_TEXEL_WIDTH;
		uv.y *= CUBEUV_TEXEL_HEIGHT;
		#ifdef texture2DGradEXT
			return texture2DGradEXT( envMap, uv, vec2( 0.0 ), vec2( 0.0 ) ).rgb;
		#else
			return texture2D( envMap, uv ).rgb;
		#endif
	}
	#define cubeUV_r0 1.0
	#define cubeUV_m0 - 2.0
	#define cubeUV_r1 0.8
	#define cubeUV_m1 - 1.0
	#define cubeUV_r4 0.4
	#define cubeUV_m4 2.0
	#define cubeUV_r5 0.305
	#define cubeUV_m5 3.0
	#define cubeUV_r6 0.21
	#define cubeUV_m6 4.0
	float roughnessToMip( float roughness ) {
		float mip = 0.0;
		if ( roughness >= cubeUV_r1 ) {
			mip = ( cubeUV_r0 - roughness ) * ( cubeUV_m1 - cubeUV_m0 ) / ( cubeUV_r0 - cubeUV_r1 ) + cubeUV_m0;
		} else if ( roughness >= cubeUV_r4 ) {
			mip = ( cubeUV_r1 - roughness ) * ( cubeUV_m4 - cubeUV_m1 ) / ( cubeUV_r1 - cubeUV_r4 ) + cubeUV_m1;
		} else if ( roughness >= cubeUV_r5 ) {
			mip = ( cubeUV_r4 - roughness ) * ( cubeUV_m5 - cubeUV_m4 ) / ( cubeUV_r4 - cubeUV_r5 ) + cubeUV_m4;
		} else if ( roughness >= cubeUV_r6 ) {
			mip = ( cubeUV_r5 - roughness ) * ( cubeUV_m6 - cubeUV_m5 ) / ( cubeUV_r5 - cubeUV_r6 ) + cubeUV_m5;
		} else {
			mip = - 2.0 * log2( 1.16 * roughness );		}
		return mip;
	}
	vec4 textureCubeUV( sampler2D envMap, vec3 sampleDir, float roughness ) {
		float mip = clamp( roughnessToMip( roughness ), cubeUV_m0, CUBEUV_MAX_MIP );
		float mipF = fract( mip );
		float mipInt = floor( mip );
		vec3 color0 = bilinearCubeUV( envMap, sampleDir, mipInt );
		if ( mipF == 0.0 ) {
			return vec4( color0, 1.0 );
		} else {
			vec3 color1 = bilinearCubeUV( envMap, sampleDir, mipInt + 1.0 );
			return vec4( mix( color0, color1, mipF ), 1.0 );
		}
	}
#endif`,defaultnormal_vertex:`vec3 transformedNormal = objectNormal;
#ifdef USE_TANGENT
	vec3 transformedTangent = objectTangent;
#endif
#ifdef USE_BATCHING
	mat3 bm = mat3( batchingMatrix );
	transformedNormal /= vec3( dot( bm[ 0 ], bm[ 0 ] ), dot( bm[ 1 ], bm[ 1 ] ), dot( bm[ 2 ], bm[ 2 ] ) );
	transformedNormal = bm * transformedNormal;
	#ifdef USE_TANGENT
		transformedTangent = bm * transformedTangent;
	#endif
#endif
#ifdef USE_INSTANCING
	mat3 im = mat3( instanceMatrix );
	transformedNormal /= vec3( dot( im[ 0 ], im[ 0 ] ), dot( im[ 1 ], im[ 1 ] ), dot( im[ 2 ], im[ 2 ] ) );
	transformedNormal = im * transformedNormal;
	#ifdef USE_TANGENT
		transformedTangent = im * transformedTangent;
	#endif
#endif
transformedNormal = normalMatrix * transformedNormal;
#ifdef FLIP_SIDED
	transformedNormal = - transformedNormal;
#endif
#ifdef USE_TANGENT
	transformedTangent = ( modelViewMatrix * vec4( transformedTangent, 0.0 ) ).xyz;
	#ifdef FLIP_SIDED
		transformedTangent = - transformedTangent;
	#endif
#endif`,displacementmap_pars_vertex:`#ifdef USE_DISPLACEMENTMAP
	uniform sampler2D displacementMap;
	uniform float displacementScale;
	uniform float displacementBias;
#endif`,displacementmap_vertex:`#ifdef USE_DISPLACEMENTMAP
	transformed += normalize( objectNormal ) * ( texture2D( displacementMap, vDisplacementMapUv ).x * displacementScale + displacementBias );
#endif`,emissivemap_fragment:`#ifdef USE_EMISSIVEMAP
	vec4 emissiveColor = texture2D( emissiveMap, vEmissiveMapUv );
	#ifdef DECODE_VIDEO_TEXTURE_EMISSIVE
		emissiveColor = sRGBTransferEOTF( emissiveColor );
	#endif
	totalEmissiveRadiance *= emissiveColor.rgb;
#endif`,emissivemap_pars_fragment:`#ifdef USE_EMISSIVEMAP
	uniform sampler2D emissiveMap;
#endif`,colorspace_fragment:`gl_FragColor = linearToOutputTexel( gl_FragColor );`,colorspace_pars_fragment:`vec4 LinearTransferOETF( in vec4 value ) {
	return value;
}
vec4 sRGBTransferEOTF( in vec4 value ) {
	return vec4( mix( pow( value.rgb * 0.9478672986 + vec3( 0.0521327014 ), vec3( 2.4 ) ), value.rgb * 0.0773993808, vec3( lessThanEqual( value.rgb, vec3( 0.04045 ) ) ) ), value.a );
}
vec4 sRGBTransferOETF( in vec4 value ) {
	return vec4( mix( pow( value.rgb, vec3( 0.41666 ) ) * 1.055 - vec3( 0.055 ), value.rgb * 12.92, vec3( lessThanEqual( value.rgb, vec3( 0.0031308 ) ) ) ), value.a );
}`,envmap_fragment:`#ifdef USE_ENVMAP
	#ifdef ENV_WORLDPOS
		vec3 cameraToFrag;
		if ( isOrthographic ) {
			cameraToFrag = normalize( vec3( - viewMatrix[ 0 ][ 2 ], - viewMatrix[ 1 ][ 2 ], - viewMatrix[ 2 ][ 2 ] ) );
		} else {
			cameraToFrag = normalize( vWorldPosition - cameraPosition );
		}
		vec3 worldNormal = inverseTransformDirection( normal, viewMatrix );
		#ifdef ENVMAP_MODE_REFLECTION
			vec3 reflectVec = reflect( cameraToFrag, worldNormal );
		#else
			vec3 reflectVec = refract( cameraToFrag, worldNormal, refractionRatio );
		#endif
	#else
		vec3 reflectVec = vReflect;
	#endif
	#ifdef ENVMAP_TYPE_CUBE
		vec4 envColor = textureCube( envMap, envMapRotation * reflectVec );
		#ifdef ENVMAP_BLENDING_MULTIPLY
			outgoingLight = mix( outgoingLight, outgoingLight * envColor.xyz, specularStrength * reflectivity );
		#elif defined( ENVMAP_BLENDING_MIX )
			outgoingLight = mix( outgoingLight, envColor.xyz, specularStrength * reflectivity );
		#elif defined( ENVMAP_BLENDING_ADD )
			outgoingLight += envColor.xyz * specularStrength * reflectivity;
		#endif
	#endif
#endif`,envmap_common_pars_fragment:`#ifdef USE_ENVMAP
	uniform float envMapIntensity;
	uniform mat3 envMapRotation;
	#ifdef ENVMAP_TYPE_CUBE
		uniform samplerCube envMap;
	#else
		uniform sampler2D envMap;
	#endif
#endif`,envmap_pars_fragment:`#ifdef USE_ENVMAP
	uniform float reflectivity;
	#if defined( USE_BUMPMAP ) || defined( USE_NORMALMAP ) || defined( PHONG ) || defined( LAMBERT )
		#define ENV_WORLDPOS
	#endif
	#ifdef ENV_WORLDPOS
		varying vec3 vWorldPosition;
		uniform float refractionRatio;
	#else
		varying vec3 vReflect;
	#endif
#endif`,envmap_pars_vertex:`#ifdef USE_ENVMAP
	#if defined( USE_BUMPMAP ) || defined( USE_NORMALMAP ) || defined( PHONG ) || defined( LAMBERT )
		#define ENV_WORLDPOS
	#endif
	#ifdef ENV_WORLDPOS
		
		varying vec3 vWorldPosition;
	#else
		varying vec3 vReflect;
		uniform float refractionRatio;
	#endif
#endif`,envmap_physical_pars_fragment:`#ifdef USE_ENVMAP
	vec3 getIBLIrradiance( const in vec3 normal ) {
		#ifdef ENVMAP_TYPE_CUBE_UV
			vec3 worldNormal = inverseTransformDirection( normal, viewMatrix );
			vec4 envMapColor = textureCubeUV( envMap, envMapRotation * worldNormal, 1.0 );
			return PI * envMapColor.rgb * envMapIntensity;
		#else
			return vec3( 0.0 );
		#endif
	}
	vec3 getIBLRadiance( const in vec3 viewDir, const in vec3 normal, const in float roughness ) {
		#ifdef ENVMAP_TYPE_CUBE_UV
			vec3 reflectVec = reflect( - viewDir, normal );
			reflectVec = normalize( mix( reflectVec, normal, pow4( roughness ) ) );
			reflectVec = inverseTransformDirection( reflectVec, viewMatrix );
			vec4 envMapColor = textureCubeUV( envMap, envMapRotation * reflectVec, roughness );
			return envMapColor.rgb * envMapIntensity;
		#else
			return vec3( 0.0 );
		#endif
	}
	#ifdef USE_ANISOTROPY
		vec3 getIBLAnisotropyRadiance( const in vec3 viewDir, const in vec3 normal, const in float roughness, const in vec3 bitangent, const in float anisotropy ) {
			#ifdef ENVMAP_TYPE_CUBE_UV
				vec3 bentNormal = cross( bitangent, viewDir );
				bentNormal = normalize( cross( bentNormal, bitangent ) );
				bentNormal = normalize( mix( bentNormal, normal, pow2( pow2( 1.0 - anisotropy * ( 1.0 - roughness ) ) ) ) );
				return getIBLRadiance( viewDir, bentNormal, roughness );
			#else
				return vec3( 0.0 );
			#endif
		}
	#endif
#endif`,envmap_vertex:`#ifdef USE_ENVMAP
	#ifdef ENV_WORLDPOS
		vWorldPosition = worldPosition.xyz;
	#else
		vec3 cameraToVertex;
		if ( isOrthographic ) {
			cameraToVertex = normalize( vec3( - viewMatrix[ 0 ][ 2 ], - viewMatrix[ 1 ][ 2 ], - viewMatrix[ 2 ][ 2 ] ) );
		} else {
			cameraToVertex = normalize( worldPosition.xyz - cameraPosition );
		}
		vec3 worldNormal = inverseTransformDirection( transformedNormal, viewMatrix );
		#ifdef ENVMAP_MODE_REFLECTION
			vReflect = reflect( cameraToVertex, worldNormal );
		#else
			vReflect = refract( cameraToVertex, worldNormal, refractionRatio );
		#endif
	#endif
#endif`,fog_vertex:`#ifdef USE_FOG
	vFogDepth = - mvPosition.z;
#endif`,fog_pars_vertex:`#ifdef USE_FOG
	varying float vFogDepth;
#endif`,fog_fragment:`#ifdef USE_FOG
	#ifdef FOG_EXP2
		float fogFactor = 1.0 - exp( - fogDensity * fogDensity * vFogDepth * vFogDepth );
	#else
		float fogFactor = smoothstep( fogNear, fogFar, vFogDepth );
	#endif
	gl_FragColor.rgb = mix( gl_FragColor.rgb, fogColor, fogFactor );
#endif`,fog_pars_fragment:`#ifdef USE_FOG
	uniform vec3 fogColor;
	varying float vFogDepth;
	#ifdef FOG_EXP2
		uniform float fogDensity;
	#else
		uniform float fogNear;
		uniform float fogFar;
	#endif
#endif`,gradientmap_pars_fragment:`#ifdef USE_GRADIENTMAP
	uniform sampler2D gradientMap;
#endif
vec3 getGradientIrradiance( vec3 normal, vec3 lightDirection ) {
	float dotNL = dot( normal, lightDirection );
	vec2 coord = vec2( dotNL * 0.5 + 0.5, 0.0 );
	#ifdef USE_GRADIENTMAP
		return vec3( texture2D( gradientMap, coord ).r );
	#else
		vec2 fw = fwidth( coord ) * 0.5;
		return mix( vec3( 0.7 ), vec3( 1.0 ), smoothstep( 0.7 - fw.x, 0.7 + fw.x, coord.x ) );
	#endif
}`,lightmap_pars_fragment:`#ifdef USE_LIGHTMAP
	uniform sampler2D lightMap;
	uniform float lightMapIntensity;
#endif`,lights_lambert_fragment:`LambertMaterial material;
material.diffuseColor = diffuseColor.rgb;
material.specularStrength = specularStrength;`,lights_lambert_pars_fragment:`varying vec3 vViewPosition;
struct LambertMaterial {
	vec3 diffuseColor;
	float specularStrength;
};
void RE_Direct_Lambert( const in IncidentLight directLight, const in vec3 geometryPosition, const in vec3 geometryNormal, const in vec3 geometryViewDir, const in vec3 geometryClearcoatNormal, const in LambertMaterial material, inout ReflectedLight reflectedLight ) {
	float dotNL = saturate( dot( geometryNormal, directLight.direction ) );
	vec3 irradiance = dotNL * directLight.color;
	reflectedLight.directDiffuse += irradiance * BRDF_Lambert( material.diffuseColor );
}
void RE_IndirectDiffuse_Lambert( const in vec3 irradiance, const in vec3 geometryPosition, const in vec3 geometryNormal, const in vec3 geometryViewDir, const in vec3 geometryClearcoatNormal, const in LambertMaterial material, inout ReflectedLight reflectedLight ) {
	reflectedLight.indirectDiffuse += irradiance * BRDF_Lambert( material.diffuseColor );
}
#define RE_Direct				RE_Direct_Lambert
#define RE_IndirectDiffuse		RE_IndirectDiffuse_Lambert`,lights_pars_begin:`uniform bool receiveShadow;
uniform vec3 ambientLightColor;
#if defined( USE_LIGHT_PROBES )
	uniform vec3 lightProbe[ 9 ];
#endif
vec3 shGetIrradianceAt( in vec3 normal, in vec3 shCoefficients[ 9 ] ) {
	float x = normal.x, y = normal.y, z = normal.z;
	vec3 result = shCoefficients[ 0 ] * 0.886227;
	result += shCoefficients[ 1 ] * 2.0 * 0.511664 * y;
	result += shCoefficients[ 2 ] * 2.0 * 0.511664 * z;
	result += shCoefficients[ 3 ] * 2.0 * 0.511664 * x;
	result += shCoefficients[ 4 ] * 2.0 * 0.429043 * x * y;
	result += shCoefficients[ 5 ] * 2.0 * 0.429043 * y * z;
	result += shCoefficients[ 6 ] * ( 0.743125 * z * z - 0.247708 );
	result += shCoefficients[ 7 ] * 2.0 * 0.429043 * x * z;
	result += shCoefficients[ 8 ] * 0.429043 * ( x * x - y * y );
	return result;
}
vec3 getLightProbeIrradiance( const in vec3 lightProbe[ 9 ], const in vec3 normal ) {
	vec3 worldNormal = inverseTransformDirection( normal, viewMatrix );
	vec3 irradiance = shGetIrradianceAt( worldNormal, lightProbe );
	return irradiance;
}
vec3 getAmbientLightIrradiance( const in vec3 ambientLightColor ) {
	vec3 irradiance = ambientLightColor;
	return irradiance;
}
float getDistanceAttenuation( const in float lightDistance, const in float cutoffDistance, const in float decayExponent ) {
	float distanceFalloff = 1.0 / max( pow( lightDistance, decayExponent ), 0.01 );
	if ( cutoffDistance > 0.0 ) {
		distanceFalloff *= pow2( saturate( 1.0 - pow4( lightDistance / cutoffDistance ) ) );
	}
	return distanceFalloff;
}
float getSpotAttenuation( const in float coneCosine, const in float penumbraCosine, const in float angleCosine ) {
	return smoothstep( coneCosine, penumbraCosine, angleCosine );
}
#if NUM_DIR_LIGHTS > 0
	struct DirectionalLight {
		vec3 direction;
		vec3 color;
	};
	uniform DirectionalLight directionalLights[ NUM_DIR_LIGHTS ];
	void getDirectionalLightInfo( const in DirectionalLight directionalLight, out IncidentLight light ) {
		light.color = directionalLight.color;
		light.direction = directionalLight.direction;
		light.visible = true;
	}
#endif
#if NUM_POINT_LIGHTS > 0
	struct PointLight {
		vec3 position;
		vec3 color;
		float distance;
		float decay;
	};
	uniform PointLight pointLights[ NUM_POINT_LIGHTS ];
	void getPointLightInfo( const in PointLight pointLight, const in vec3 geometryPosition, out IncidentLight light ) {
		vec3 lVector = pointLight.position - geometryPosition;
		light.direction = normalize( lVector );
		float lightDistance = length( lVector );
		light.color = pointLight.color;
		light.color *= getDistanceAttenuation( lightDistance, pointLight.distance, pointLight.decay );
		light.visible = ( light.color != vec3( 0.0 ) );
	}
#endif
#if NUM_SPOT_LIGHTS > 0
	struct SpotLight {
		vec3 position;
		vec3 direction;
		vec3 color;
		float distance;
		float decay;
		float coneCos;
		float penumbraCos;
	};
	uniform SpotLight spotLights[ NUM_SPOT_LIGHTS ];
	void getSpotLightInfo( const in SpotLight spotLight, const in vec3 geometryPosition, out IncidentLight light ) {
		vec3 lVector = spotLight.position - geometryPosition;
		light.direction = normalize( lVector );
		float angleCos = dot( light.direction, spotLight.direction );
		float spotAttenuation = getSpotAttenuation( spotLight.coneCos, spotLight.penumbraCos, angleCos );
		if ( spotAttenuation > 0.0 ) {
			float lightDistance = length( lVector );
			light.color = spotLight.color * spotAttenuation;
			light.color *= getDistanceAttenuation( lightDistance, spotLight.distance, spotLight.decay );
			light.visible = ( light.color != vec3( 0.0 ) );
		} else {
			light.color = vec3( 0.0 );
			light.visible = false;
		}
	}
#endif
#if NUM_RECT_AREA_LIGHTS > 0
	struct RectAreaLight {
		vec3 color;
		vec3 position;
		vec3 halfWidth;
		vec3 halfHeight;
	};
	uniform sampler2D ltc_1;	uniform sampler2D ltc_2;
	uniform RectAreaLight rectAreaLights[ NUM_RECT_AREA_LIGHTS ];
#endif
#if NUM_HEMI_LIGHTS > 0
	struct HemisphereLight {
		vec3 direction;
		vec3 skyColor;
		vec3 groundColor;
	};
	uniform HemisphereLight hemisphereLights[ NUM_HEMI_LIGHTS ];
	vec3 getHemisphereLightIrradiance( const in HemisphereLight hemiLight, const in vec3 normal ) {
		float dotNL = dot( normal, hemiLight.direction );
		float hemiDiffuseWeight = 0.5 * dotNL + 0.5;
		vec3 irradiance = mix( hemiLight.groundColor, hemiLight.skyColor, hemiDiffuseWeight );
		return irradiance;
	}
#endif
#include <lightprobes_pars_fragment>`,lights_toon_fragment:`ToonMaterial material;
material.diffuseColor = diffuseColor.rgb;`,lights_toon_pars_fragment:`varying vec3 vViewPosition;
struct ToonMaterial {
	vec3 diffuseColor;
};
void RE_Direct_Toon( const in IncidentLight directLight, const in vec3 geometryPosition, const in vec3 geometryNormal, const in vec3 geometryViewDir, const in vec3 geometryClearcoatNormal, const in ToonMaterial material, inout ReflectedLight reflectedLight ) {
	vec3 irradiance = getGradientIrradiance( geometryNormal, directLight.direction ) * directLight.color;
	reflectedLight.directDiffuse += irradiance * BRDF_Lambert( material.diffuseColor );
}
void RE_IndirectDiffuse_Toon( const in vec3 irradiance, const in vec3 geometryPosition, const in vec3 geometryNormal, const in vec3 geometryViewDir, const in vec3 geometryClearcoatNormal, const in ToonMaterial material, inout ReflectedLight reflectedLight ) {
	reflectedLight.indirectDiffuse += irradiance * BRDF_Lambert( material.diffuseColor );
}
#define RE_Direct				RE_Direct_Toon
#define RE_IndirectDiffuse		RE_IndirectDiffuse_Toon`,lights_phong_fragment:`BlinnPhongMaterial material;
material.diffuseColor = diffuseColor.rgb;
material.specularColor = specular;
material.specularShininess = shininess;
material.specularStrength = specularStrength;`,lights_phong_pars_fragment:`varying vec3 vViewPosition;
struct BlinnPhongMaterial {
	vec3 diffuseColor;
	vec3 specularColor;
	float specularShininess;
	float specularStrength;
};
void RE_Direct_BlinnPhong( const in IncidentLight directLight, const in vec3 geometryPosition, const in vec3 geometryNormal, const in vec3 geometryViewDir, const in vec3 geometryClearcoatNormal, const in BlinnPhongMaterial material, inout ReflectedLight reflectedLight ) {
	float dotNL = saturate( dot( geometryNormal, directLight.direction ) );
	vec3 irradiance = dotNL * directLight.color;
	reflectedLight.directDiffuse += irradiance * BRDF_Lambert( material.diffuseColor );
	reflectedLight.directSpecular += irradiance * BRDF_BlinnPhong( directLight.direction, geometryViewDir, geometryNormal, material.specularColor, material.specularShininess ) * material.specularStrength;
}
void RE_IndirectDiffuse_BlinnPhong( const in vec3 irradiance, const in vec3 geometryPosition, const in vec3 geometryNormal, const in vec3 geometryViewDir, const in vec3 geometryClearcoatNormal, const in BlinnPhongMaterial material, inout ReflectedLight reflectedLight ) {
	reflectedLight.indirectDiffuse += irradiance * BRDF_Lambert( material.diffuseColor );
}
#define RE_Direct				RE_Direct_BlinnPhong
#define RE_IndirectDiffuse		RE_IndirectDiffuse_BlinnPhong`,lights_physical_fragment:`PhysicalMaterial material;
material.diffuseColor = diffuseColor.rgb;
material.diffuseContribution = diffuseColor.rgb * ( 1.0 - metalnessFactor );
material.metalness = metalnessFactor;
vec3 dxy = max( abs( dFdx( nonPerturbedNormal ) ), abs( dFdy( nonPerturbedNormal ) ) );
float geometryRoughness = max( max( dxy.x, dxy.y ), dxy.z );
material.roughness = max( roughnessFactor, 0.0525 );material.roughness += geometryRoughness;
material.roughness = min( material.roughness, 1.0 );
#ifdef IOR
	material.ior = ior;
	#ifdef USE_SPECULAR
		float specularIntensityFactor = specularIntensity;
		vec3 specularColorFactor = specularColor;
		#ifdef USE_SPECULAR_COLORMAP
			specularColorFactor *= texture2D( specularColorMap, vSpecularColorMapUv ).rgb;
		#endif
		#ifdef USE_SPECULAR_INTENSITYMAP
			specularIntensityFactor *= texture2D( specularIntensityMap, vSpecularIntensityMapUv ).a;
		#endif
		material.specularF90 = mix( specularIntensityFactor, 1.0, metalnessFactor );
	#else
		float specularIntensityFactor = 1.0;
		vec3 specularColorFactor = vec3( 1.0 );
		material.specularF90 = 1.0;
	#endif
	material.specularColor = min( pow2( ( material.ior - 1.0 ) / ( material.ior + 1.0 ) ) * specularColorFactor, vec3( 1.0 ) ) * specularIntensityFactor;
	material.specularColorBlended = mix( material.specularColor, diffuseColor.rgb, metalnessFactor );
#else
	material.specularColor = vec3( 0.04 );
	material.specularColorBlended = mix( material.specularColor, diffuseColor.rgb, metalnessFactor );
	material.specularF90 = 1.0;
#endif
#ifdef USE_CLEARCOAT
	material.clearcoat = clearcoat;
	material.clearcoatRoughness = clearcoatRoughness;
	material.clearcoatF0 = vec3( 0.04 );
	material.clearcoatF90 = 1.0;
	#ifdef USE_CLEARCOATMAP
		material.clearcoat *= texture2D( clearcoatMap, vClearcoatMapUv ).x;
	#endif
	#ifdef USE_CLEARCOAT_ROUGHNESSMAP
		material.clearcoatRoughness *= texture2D( clearcoatRoughnessMap, vClearcoatRoughnessMapUv ).y;
	#endif
	material.clearcoat = saturate( material.clearcoat );	material.clearcoatRoughness = max( material.clearcoatRoughness, 0.0525 );
	material.clearcoatRoughness += geometryRoughness;
	material.clearcoatRoughness = min( material.clearcoatRoughness, 1.0 );
#endif
#ifdef USE_DISPERSION
	material.dispersion = dispersion;
#endif
#ifdef USE_IRIDESCENCE
	material.iridescence = iridescence;
	material.iridescenceIOR = iridescenceIOR;
	#ifdef USE_IRIDESCENCEMAP
		material.iridescence *= texture2D( iridescenceMap, vIridescenceMapUv ).r;
	#endif
	#ifdef USE_IRIDESCENCE_THICKNESSMAP
		material.iridescenceThickness = (iridescenceThicknessMaximum - iridescenceThicknessMinimum) * texture2D( iridescenceThicknessMap, vIridescenceThicknessMapUv ).g + iridescenceThicknessMinimum;
	#else
		material.iridescenceThickness = iridescenceThicknessMaximum;
	#endif
#endif
#ifdef USE_SHEEN
	material.sheenColor = sheenColor;
	#ifdef USE_SHEEN_COLORMAP
		material.sheenColor *= texture2D( sheenColorMap, vSheenColorMapUv ).rgb;
	#endif
	material.sheenRoughness = clamp( sheenRoughness, 0.0001, 1.0 );
	#ifdef USE_SHEEN_ROUGHNESSMAP
		material.sheenRoughness *= texture2D( sheenRoughnessMap, vSheenRoughnessMapUv ).a;
	#endif
#endif
#ifdef USE_ANISOTROPY
	#ifdef USE_ANISOTROPYMAP
		mat2 anisotropyMat = mat2( anisotropyVector.x, anisotropyVector.y, - anisotropyVector.y, anisotropyVector.x );
		vec3 anisotropyPolar = texture2D( anisotropyMap, vAnisotropyMapUv ).rgb;
		vec2 anisotropyV = anisotropyMat * normalize( 2.0 * anisotropyPolar.rg - vec2( 1.0 ) ) * anisotropyPolar.b;
	#else
		vec2 anisotropyV = anisotropyVector;
	#endif
	material.anisotropy = length( anisotropyV );
	if( material.anisotropy == 0.0 ) {
		anisotropyV = vec2( 1.0, 0.0 );
	} else {
		anisotropyV /= material.anisotropy;
		material.anisotropy = saturate( material.anisotropy );
	}
	material.alphaT = mix( pow2( material.roughness ), 1.0, pow2( material.anisotropy ) );
	material.anisotropyT = tbn[ 0 ] * anisotropyV.x + tbn[ 1 ] * anisotropyV.y;
	material.anisotropyB = tbn[ 1 ] * anisotropyV.x - tbn[ 0 ] * anisotropyV.y;
#endif`,lights_physical_pars_fragment:`uniform sampler2D dfgLUT;
struct PhysicalMaterial {
	vec3 diffuseColor;
	vec3 diffuseContribution;
	vec3 specularColor;
	vec3 specularColorBlended;
	float roughness;
	float metalness;
	float specularF90;
	float dispersion;
	#ifdef USE_CLEARCOAT
		float clearcoat;
		float clearcoatRoughness;
		vec3 clearcoatF0;
		float clearcoatF90;
	#endif
	#ifdef USE_IRIDESCENCE
		float iridescence;
		float iridescenceIOR;
		float iridescenceThickness;
		vec3 iridescenceFresnel;
		vec3 iridescenceF0;
		vec3 iridescenceFresnelDielectric;
		vec3 iridescenceFresnelMetallic;
	#endif
	#ifdef USE_SHEEN
		vec3 sheenColor;
		float sheenRoughness;
	#endif
	#ifdef IOR
		float ior;
	#endif
	#ifdef USE_TRANSMISSION
		float transmission;
		float transmissionAlpha;
		float thickness;
		float attenuationDistance;
		vec3 attenuationColor;
	#endif
	#ifdef USE_ANISOTROPY
		float anisotropy;
		float alphaT;
		vec3 anisotropyT;
		vec3 anisotropyB;
	#endif
};
vec3 clearcoatSpecularDirect = vec3( 0.0 );
vec3 clearcoatSpecularIndirect = vec3( 0.0 );
vec3 sheenSpecularDirect = vec3( 0.0 );
vec3 sheenSpecularIndirect = vec3(0.0 );
vec3 Schlick_to_F0( const in vec3 f, const in float f90, const in float dotVH ) {
    float x = clamp( 1.0 - dotVH, 0.0, 1.0 );
    float x2 = x * x;
    float x5 = clamp( x * x2 * x2, 0.0, 0.9999 );
    return ( f - vec3( f90 ) * x5 ) / ( 1.0 - x5 );
}
float V_GGX_SmithCorrelated( const in float alpha, const in float dotNL, const in float dotNV ) {
	float a2 = pow2( alpha );
	float gv = dotNL * sqrt( a2 + ( 1.0 - a2 ) * pow2( dotNV ) );
	float gl = dotNV * sqrt( a2 + ( 1.0 - a2 ) * pow2( dotNL ) );
	return 0.5 / max( gv + gl, EPSILON );
}
float D_GGX( const in float alpha, const in float dotNH ) {
	float a2 = pow2( alpha );
	float denom = pow2( dotNH ) * ( a2 - 1.0 ) + 1.0;
	return RECIPROCAL_PI * a2 / pow2( denom );
}
#ifdef USE_ANISOTROPY
	float V_GGX_SmithCorrelated_Anisotropic( const in float alphaT, const in float alphaB, const in float dotTV, const in float dotBV, const in float dotTL, const in float dotBL, const in float dotNV, const in float dotNL ) {
		float gv = dotNL * length( vec3( alphaT * dotTV, alphaB * dotBV, dotNV ) );
		float gl = dotNV * length( vec3( alphaT * dotTL, alphaB * dotBL, dotNL ) );
		return 0.5 / max( gv + gl, EPSILON );
	}
	float D_GGX_Anisotropic( const in float alphaT, const in float alphaB, const in float dotNH, const in float dotTH, const in float dotBH ) {
		float a2 = alphaT * alphaB;
		highp vec3 v = vec3( alphaB * dotTH, alphaT * dotBH, a2 * dotNH );
		highp float v2 = dot( v, v );
		float w2 = a2 / v2;
		return RECIPROCAL_PI * a2 * pow2 ( w2 );
	}
#endif
#ifdef USE_CLEARCOAT
	vec3 BRDF_GGX_Clearcoat( const in vec3 lightDir, const in vec3 viewDir, const in vec3 normal, const in PhysicalMaterial material) {
		vec3 f0 = material.clearcoatF0;
		float f90 = material.clearcoatF90;
		float roughness = material.clearcoatRoughness;
		float alpha = pow2( roughness );
		vec3 halfDir = normalize( lightDir + viewDir );
		float dotNL = saturate( dot( normal, lightDir ) );
		float dotNV = saturate( dot( normal, viewDir ) );
		float dotNH = saturate( dot( normal, halfDir ) );
		float dotVH = saturate( dot( viewDir, halfDir ) );
		vec3 F = F_Schlick( f0, f90, dotVH );
		float V = V_GGX_SmithCorrelated( alpha, dotNL, dotNV );
		float D = D_GGX( alpha, dotNH );
		return F * ( V * D );
	}
#endif
vec3 BRDF_GGX( const in vec3 lightDir, const in vec3 viewDir, const in vec3 normal, const in PhysicalMaterial material ) {
	vec3 f0 = material.specularColorBlended;
	float f90 = material.specularF90;
	float roughness = material.roughness;
	float alpha = pow2( roughness );
	vec3 halfDir = normalize( lightDir + viewDir );
	float dotNL = saturate( dot( normal, lightDir ) );
	float dotNV = saturate( dot( normal, viewDir ) );
	float dotNH = saturate( dot( normal, halfDir ) );
	float dotVH = saturate( dot( viewDir, halfDir ) );
	vec3 F = F_Schlick( f0, f90, dotVH );
	#ifdef USE_IRIDESCENCE
		F = mix( F, material.iridescenceFresnel, material.iridescence );
	#endif
	#ifdef USE_ANISOTROPY
		float dotTL = dot( material.anisotropyT, lightDir );
		float dotTV = dot( material.anisotropyT, viewDir );
		float dotTH = dot( material.anisotropyT, halfDir );
		float dotBL = dot( material.anisotropyB, lightDir );
		float dotBV = dot( material.anisotropyB, viewDir );
		float dotBH = dot( material.anisotropyB, halfDir );
		float V = V_GGX_SmithCorrelated_Anisotropic( material.alphaT, alpha, dotTV, dotBV, dotTL, dotBL, dotNV, dotNL );
		float D = D_GGX_Anisotropic( material.alphaT, alpha, dotNH, dotTH, dotBH );
	#else
		float V = V_GGX_SmithCorrelated( alpha, dotNL, dotNV );
		float D = D_GGX( alpha, dotNH );
	#endif
	return F * ( V * D );
}
vec2 LTC_Uv( const in vec3 N, const in vec3 V, const in float roughness ) {
	const float LUT_SIZE = 64.0;
	const float LUT_SCALE = ( LUT_SIZE - 1.0 ) / LUT_SIZE;
	const float LUT_BIAS = 0.5 / LUT_SIZE;
	float dotNV = saturate( dot( N, V ) );
	vec2 uv = vec2( roughness, sqrt( 1.0 - dotNV ) );
	uv = uv * LUT_SCALE + LUT_BIAS;
	return uv;
}
float LTC_ClippedSphereFormFactor( const in vec3 f ) {
	float l = length( f );
	return max( ( l * l + f.z ) / ( l + 1.0 ), 0.0 );
}
vec3 LTC_EdgeVectorFormFactor( const in vec3 v1, const in vec3 v2 ) {
	float x = dot( v1, v2 );
	float y = abs( x );
	float a = 0.8543985 + ( 0.4965155 + 0.0145206 * y ) * y;
	float b = 3.4175940 + ( 4.1616724 + y ) * y;
	float v = a / b;
	float theta_sintheta = ( x > 0.0 ) ? v : 0.5 * inversesqrt( max( 1.0 - x * x, 1e-7 ) ) - v;
	return cross( v1, v2 ) * theta_sintheta;
}
vec3 LTC_Evaluate( const in vec3 N, const in vec3 V, const in vec3 P, const in mat3 mInv, const in vec3 rectCoords[ 4 ] ) {
	vec3 v1 = rectCoords[ 1 ] - rectCoords[ 0 ];
	vec3 v2 = rectCoords[ 3 ] - rectCoords[ 0 ];
	vec3 lightNormal = cross( v1, v2 );
	if( dot( lightNormal, P - rectCoords[ 0 ] ) < 0.0 ) return vec3( 0.0 );
	vec3 T1, T2;
	T1 = normalize( V - N * dot( V, N ) );
	T2 = - cross( N, T1 );
	mat3 mat = mInv * transpose( mat3( T1, T2, N ) );
	vec3 coords[ 4 ];
	coords[ 0 ] = mat * ( rectCoords[ 0 ] - P );
	coords[ 1 ] = mat * ( rectCoords[ 1 ] - P );
	coords[ 2 ] = mat * ( rectCoords[ 2 ] - P );
	coords[ 3 ] = mat * ( rectCoords[ 3 ] - P );
	coords[ 0 ] = normalize( coords[ 0 ] );
	coords[ 1 ] = normalize( coords[ 1 ] );
	coords[ 2 ] = normalize( coords[ 2 ] );
	coords[ 3 ] = normalize( coords[ 3 ] );
	vec3 vectorFormFactor = vec3( 0.0 );
	vectorFormFactor += LTC_EdgeVectorFormFactor( coords[ 0 ], coords[ 1 ] );
	vectorFormFactor += LTC_EdgeVectorFormFactor( coords[ 1 ], coords[ 2 ] );
	vectorFormFactor += LTC_EdgeVectorFormFactor( coords[ 2 ], coords[ 3 ] );
	vectorFormFactor += LTC_EdgeVectorFormFactor( coords[ 3 ], coords[ 0 ] );
	float result = LTC_ClippedSphereFormFactor( vectorFormFactor );
	return vec3( result );
}
#if defined( USE_SHEEN )
float D_Charlie( float roughness, float dotNH ) {
	float alpha = pow2( roughness );
	float invAlpha = 1.0 / alpha;
	float cos2h = dotNH * dotNH;
	float sin2h = max( 1.0 - cos2h, 0.0078125 );
	return ( 2.0 + invAlpha ) * pow( sin2h, invAlpha * 0.5 ) / ( 2.0 * PI );
}
float V_Neubelt( float dotNV, float dotNL ) {
	return saturate( 1.0 / ( 4.0 * ( dotNL + dotNV - dotNL * dotNV ) ) );
}
vec3 BRDF_Sheen( const in vec3 lightDir, const in vec3 viewDir, const in vec3 normal, vec3 sheenColor, const in float sheenRoughness ) {
	vec3 halfDir = normalize( lightDir + viewDir );
	float dotNL = saturate( dot( normal, lightDir ) );
	float dotNV = saturate( dot( normal, viewDir ) );
	float dotNH = saturate( dot( normal, halfDir ) );
	float D = D_Charlie( sheenRoughness, dotNH );
	float V = V_Neubelt( dotNV, dotNL );
	return sheenColor * ( D * V );
}
#endif
float IBLSheenBRDF( const in vec3 normal, const in vec3 viewDir, const in float roughness ) {
	float dotNV = saturate( dot( normal, viewDir ) );
	float r2 = roughness * roughness;
	float rInv = 1.0 / ( roughness + 0.1 );
	float a = -1.9362 + 1.0678 * roughness + 0.4573 * r2 - 0.8469 * rInv;
	float b = -0.6014 + 0.5538 * roughness - 0.4670 * r2 - 0.1255 * rInv;
	float DG = exp( a * dotNV + b );
	return saturate( DG );
}
vec3 EnvironmentBRDF( const in vec3 normal, const in vec3 viewDir, const in vec3 specularColor, const in float specularF90, const in float roughness ) {
	float dotNV = saturate( dot( normal, viewDir ) );
	vec2 fab = texture2D( dfgLUT, vec2( roughness, dotNV ) ).rg;
	return specularColor * fab.x + specularF90 * fab.y;
}
#ifdef USE_IRIDESCENCE
void computeMultiscatteringIridescence( const in vec3 normal, const in vec3 viewDir, const in vec3 specularColor, const in float specularF90, const in float iridescence, const in vec3 iridescenceF0, const in float roughness, inout vec3 singleScatter, inout vec3 multiScatter ) {
#else
void computeMultiscattering( const in vec3 normal, const in vec3 viewDir, const in vec3 specularColor, const in float specularF90, const in float roughness, inout vec3 singleScatter, inout vec3 multiScatter ) {
#endif
	float dotNV = saturate( dot( normal, viewDir ) );
	vec2 fab = texture2D( dfgLUT, vec2( roughness, dotNV ) ).rg;
	#ifdef USE_IRIDESCENCE
		vec3 Fr = mix( specularColor, iridescenceF0, iridescence );
	#else
		vec3 Fr = specularColor;
	#endif
	vec3 FssEss = Fr * fab.x + specularF90 * fab.y;
	float Ess = fab.x + fab.y;
	float Ems = 1.0 - Ess;
	vec3 Favg = Fr + ( 1.0 - Fr ) * 0.047619;	vec3 Fms = FssEss * Favg / ( 1.0 - Ems * Favg );
	singleScatter += FssEss;
	multiScatter += Fms * Ems;
}
vec3 BRDF_GGX_Multiscatter( const in vec3 lightDir, const in vec3 viewDir, const in vec3 normal, const in PhysicalMaterial material ) {
	vec3 singleScatter = BRDF_GGX( lightDir, viewDir, normal, material );
	float dotNL = saturate( dot( normal, lightDir ) );
	float dotNV = saturate( dot( normal, viewDir ) );
	vec2 dfgV = texture2D( dfgLUT, vec2( material.roughness, dotNV ) ).rg;
	vec2 dfgL = texture2D( dfgLUT, vec2( material.roughness, dotNL ) ).rg;
	vec3 FssEss_V = material.specularColorBlended * dfgV.x + material.specularF90 * dfgV.y;
	vec3 FssEss_L = material.specularColorBlended * dfgL.x + material.specularF90 * dfgL.y;
	float Ess_V = dfgV.x + dfgV.y;
	float Ess_L = dfgL.x + dfgL.y;
	float Ems_V = 1.0 - Ess_V;
	float Ems_L = 1.0 - Ess_L;
	vec3 Favg = material.specularColorBlended + ( 1.0 - material.specularColorBlended ) * 0.047619;
	vec3 Fms = FssEss_V * FssEss_L * Favg / ( 1.0 - Ems_V * Ems_L * Favg + EPSILON );
	float compensationFactor = Ems_V * Ems_L;
	vec3 multiScatter = Fms * compensationFactor;
	return singleScatter + multiScatter;
}
#if NUM_RECT_AREA_LIGHTS > 0
	void RE_Direct_RectArea_Physical( const in RectAreaLight rectAreaLight, const in vec3 geometryPosition, const in vec3 geometryNormal, const in vec3 geometryViewDir, const in vec3 geometryClearcoatNormal, const in PhysicalMaterial material, inout ReflectedLight reflectedLight ) {
		vec3 normal = geometryNormal;
		vec3 viewDir = geometryViewDir;
		vec3 position = geometryPosition;
		vec3 lightPos = rectAreaLight.position;
		vec3 halfWidth = rectAreaLight.halfWidth;
		vec3 halfHeight = rectAreaLight.halfHeight;
		vec3 lightColor = rectAreaLight.color;
		float roughness = material.roughness;
		vec3 rectCoords[ 4 ];
		rectCoords[ 0 ] = lightPos + halfWidth - halfHeight;		rectCoords[ 1 ] = lightPos - halfWidth - halfHeight;
		rectCoords[ 2 ] = lightPos - halfWidth + halfHeight;
		rectCoords[ 3 ] = lightPos + halfWidth + halfHeight;
		vec2 uv = LTC_Uv( normal, viewDir, roughness );
		vec4 t1 = texture2D( ltc_1, uv );
		vec4 t2 = texture2D( ltc_2, uv );
		mat3 mInv = mat3(
			vec3( t1.x, 0, t1.y ),
			vec3(    0, 1,    0 ),
			vec3( t1.z, 0, t1.w )
		);
		vec3 fresnel = ( material.specularColorBlended * t2.x + ( material.specularF90 - material.specularColorBlended ) * t2.y );
		reflectedLight.directSpecular += lightColor * fresnel * LTC_Evaluate( normal, viewDir, position, mInv, rectCoords );
		reflectedLight.directDiffuse += lightColor * material.diffuseContribution * LTC_Evaluate( normal, viewDir, position, mat3( 1.0 ), rectCoords );
		#ifdef USE_CLEARCOAT
			vec3 Ncc = geometryClearcoatNormal;
			vec2 uvClearcoat = LTC_Uv( Ncc, viewDir, material.clearcoatRoughness );
			vec4 t1Clearcoat = texture2D( ltc_1, uvClearcoat );
			vec4 t2Clearcoat = texture2D( ltc_2, uvClearcoat );
			mat3 mInvClearcoat = mat3(
				vec3( t1Clearcoat.x, 0, t1Clearcoat.y ),
				vec3(             0, 1,             0 ),
				vec3( t1Clearcoat.z, 0, t1Clearcoat.w )
			);
			vec3 fresnelClearcoat = material.clearcoatF0 * t2Clearcoat.x + ( material.clearcoatF90 - material.clearcoatF0 ) * t2Clearcoat.y;
			clearcoatSpecularDirect += lightColor * fresnelClearcoat * LTC_Evaluate( Ncc, viewDir, position, mInvClearcoat, rectCoords );
		#endif
	}
#endif
void RE_Direct_Physical( const in IncidentLight directLight, const in vec3 geometryPosition, const in vec3 geometryNormal, const in vec3 geometryViewDir, const in vec3 geometryClearcoatNormal, const in PhysicalMaterial material, inout ReflectedLight reflectedLight ) {
	float dotNL = saturate( dot( geometryNormal, directLight.direction ) );
	vec3 irradiance = dotNL * directLight.color;
	#ifdef USE_CLEARCOAT
		float dotNLcc = saturate( dot( geometryClearcoatNormal, directLight.direction ) );
		vec3 ccIrradiance = dotNLcc * directLight.color;
		clearcoatSpecularDirect += ccIrradiance * BRDF_GGX_Clearcoat( directLight.direction, geometryViewDir, geometryClearcoatNormal, material );
	#endif
	#ifdef USE_SHEEN
 
 		sheenSpecularDirect += irradiance * BRDF_Sheen( directLight.direction, geometryViewDir, geometryNormal, material.sheenColor, material.sheenRoughness );
 
 		float sheenAlbedoV = IBLSheenBRDF( geometryNormal, geometryViewDir, material.sheenRoughness );
 		float sheenAlbedoL = IBLSheenBRDF( geometryNormal, directLight.direction, material.sheenRoughness );
 
 		float sheenEnergyComp = 1.0 - max3( material.sheenColor ) * max( sheenAlbedoV, sheenAlbedoL );
 
 		irradiance *= sheenEnergyComp;
 
 	#endif
	reflectedLight.directSpecular += irradiance * BRDF_GGX_Multiscatter( directLight.direction, geometryViewDir, geometryNormal, material );
	reflectedLight.directDiffuse += irradiance * BRDF_Lambert( material.diffuseContribution );
}
void RE_IndirectDiffuse_Physical( const in vec3 irradiance, const in vec3 geometryPosition, const in vec3 geometryNormal, const in vec3 geometryViewDir, const in vec3 geometryClearcoatNormal, const in PhysicalMaterial material, inout ReflectedLight reflectedLight ) {
	vec3 diffuse = irradiance * BRDF_Lambert( material.diffuseContribution );
	#ifdef USE_SHEEN
		float sheenAlbedo = IBLSheenBRDF( geometryNormal, geometryViewDir, material.sheenRoughness );
		float sheenEnergyComp = 1.0 - max3( material.sheenColor ) * sheenAlbedo;
		diffuse *= sheenEnergyComp;
	#endif
	reflectedLight.indirectDiffuse += diffuse;
}
void RE_IndirectSpecular_Physical( const in vec3 radiance, const in vec3 irradiance, const in vec3 clearcoatRadiance, const in vec3 geometryPosition, const in vec3 geometryNormal, const in vec3 geometryViewDir, const in vec3 geometryClearcoatNormal, const in PhysicalMaterial material, inout ReflectedLight reflectedLight) {
	#ifdef USE_CLEARCOAT
		clearcoatSpecularIndirect += clearcoatRadiance * EnvironmentBRDF( geometryClearcoatNormal, geometryViewDir, material.clearcoatF0, material.clearcoatF90, material.clearcoatRoughness );
	#endif
	#ifdef USE_SHEEN
		sheenSpecularIndirect += irradiance * material.sheenColor * IBLSheenBRDF( geometryNormal, geometryViewDir, material.sheenRoughness ) * RECIPROCAL_PI;
 	#endif
	vec3 singleScatteringDielectric = vec3( 0.0 );
	vec3 multiScatteringDielectric = vec3( 0.0 );
	vec3 singleScatteringMetallic = vec3( 0.0 );
	vec3 multiScatteringMetallic = vec3( 0.0 );
	#ifdef USE_IRIDESCENCE
		computeMultiscatteringIridescence( geometryNormal, geometryViewDir, material.specularColor, material.specularF90, material.iridescence, material.iridescenceFresnelDielectric, material.roughness, singleScatteringDielectric, multiScatteringDielectric );
		computeMultiscatteringIridescence( geometryNormal, geometryViewDir, material.diffuseColor, material.specularF90, material.iridescence, material.iridescenceFresnelMetallic, material.roughness, singleScatteringMetallic, multiScatteringMetallic );
	#else
		computeMultiscattering( geometryNormal, geometryViewDir, material.specularColor, material.specularF90, material.roughness, singleScatteringDielectric, multiScatteringDielectric );
		computeMultiscattering( geometryNormal, geometryViewDir, material.diffuseColor, material.specularF90, material.roughness, singleScatteringMetallic, multiScatteringMetallic );
	#endif
	vec3 singleScattering = mix( singleScatteringDielectric, singleScatteringMetallic, material.metalness );
	vec3 multiScattering = mix( multiScatteringDielectric, multiScatteringMetallic, material.metalness );
	vec3 totalScatteringDielectric = singleScatteringDielectric + multiScatteringDielectric;
	vec3 diffuse = material.diffuseContribution * ( 1.0 - totalScatteringDielectric );
	vec3 cosineWeightedIrradiance = irradiance * RECIPROCAL_PI;
	vec3 indirectSpecular = radiance * singleScattering;
	indirectSpecular += multiScattering * cosineWeightedIrradiance;
	vec3 indirectDiffuse = diffuse * cosineWeightedIrradiance;
	#ifdef USE_SHEEN
		float sheenAlbedo = IBLSheenBRDF( geometryNormal, geometryViewDir, material.sheenRoughness );
		float sheenEnergyComp = 1.0 - max3( material.sheenColor ) * sheenAlbedo;
		indirectSpecular *= sheenEnergyComp;
		indirectDiffuse *= sheenEnergyComp;
	#endif
	reflectedLight.indirectSpecular += indirectSpecular;
	reflectedLight.indirectDiffuse += indirectDiffuse;
}
#define RE_Direct				RE_Direct_Physical
#define RE_Direct_RectArea		RE_Direct_RectArea_Physical
#define RE_IndirectDiffuse		RE_IndirectDiffuse_Physical
#define RE_IndirectSpecular		RE_IndirectSpecular_Physical
float computeSpecularOcclusion( const in float dotNV, const in float ambientOcclusion, const in float roughness ) {
	return saturate( pow( dotNV + ambientOcclusion, exp2( - 16.0 * roughness - 1.0 ) ) - 1.0 + ambientOcclusion );
}`,lights_fragment_begin:`
vec3 geometryPosition = - vViewPosition;
vec3 geometryNormal = normal;
vec3 geometryViewDir = ( isOrthographic ) ? vec3( 0, 0, 1 ) : normalize( vViewPosition );
vec3 geometryClearcoatNormal = vec3( 0.0 );
#ifdef USE_CLEARCOAT
	geometryClearcoatNormal = clearcoatNormal;
#endif
#ifdef USE_IRIDESCENCE
	float dotNVi = saturate( dot( normal, geometryViewDir ) );
	if ( material.iridescenceThickness == 0.0 ) {
		material.iridescence = 0.0;
	} else {
		material.iridescence = saturate( material.iridescence );
	}
	if ( material.iridescence > 0.0 ) {
		material.iridescenceFresnelDielectric = evalIridescence( 1.0, material.iridescenceIOR, dotNVi, material.iridescenceThickness, material.specularColor );
		material.iridescenceFresnelMetallic = evalIridescence( 1.0, material.iridescenceIOR, dotNVi, material.iridescenceThickness, material.diffuseColor );
		material.iridescenceFresnel = mix( material.iridescenceFresnelDielectric, material.iridescenceFresnelMetallic, material.metalness );
		material.iridescenceF0 = Schlick_to_F0( material.iridescenceFresnel, 1.0, dotNVi );
	}
#endif
IncidentLight directLight;
#if ( NUM_POINT_LIGHTS > 0 ) && defined( RE_Direct )
	PointLight pointLight;
	#if defined( USE_SHADOWMAP ) && NUM_POINT_LIGHT_SHADOWS > 0
	PointLightShadow pointLightShadow;
	#endif
	#pragma unroll_loop_start
	for ( int i = 0; i < NUM_POINT_LIGHTS; i ++ ) {
		pointLight = pointLights[ i ];
		getPointLightInfo( pointLight, geometryPosition, directLight );
		#if defined( USE_SHADOWMAP ) && ( UNROLLED_LOOP_INDEX < NUM_POINT_LIGHT_SHADOWS ) && ( defined( SHADOWMAP_TYPE_PCF ) || defined( SHADOWMAP_TYPE_BASIC ) )
		pointLightShadow = pointLightShadows[ i ];
		directLight.color *= ( directLight.visible && receiveShadow ) ? getPointShadow( pointShadowMap[ i ], pointLightShadow.shadowMapSize, pointLightShadow.shadowIntensity, pointLightShadow.shadowBias, pointLightShadow.shadowRadius, vPointShadowCoord[ i ], pointLightShadow.shadowCameraNear, pointLightShadow.shadowCameraFar ) : 1.0;
		#endif
		RE_Direct( directLight, geometryPosition, geometryNormal, geometryViewDir, geometryClearcoatNormal, material, reflectedLight );
	}
	#pragma unroll_loop_end
#endif
#if ( NUM_SPOT_LIGHTS > 0 ) && defined( RE_Direct )
	SpotLight spotLight;
	vec4 spotColor;
	vec3 spotLightCoord;
	bool inSpotLightMap;
	#if defined( USE_SHADOWMAP ) && NUM_SPOT_LIGHT_SHADOWS > 0
	SpotLightShadow spotLightShadow;
	#endif
	#pragma unroll_loop_start
	for ( int i = 0; i < NUM_SPOT_LIGHTS; i ++ ) {
		spotLight = spotLights[ i ];
		getSpotLightInfo( spotLight, geometryPosition, directLight );
		#if ( UNROLLED_LOOP_INDEX < NUM_SPOT_LIGHT_SHADOWS_WITH_MAPS )
		#define SPOT_LIGHT_MAP_INDEX UNROLLED_LOOP_INDEX
		#elif ( UNROLLED_LOOP_INDEX < NUM_SPOT_LIGHT_SHADOWS )
		#define SPOT_LIGHT_MAP_INDEX NUM_SPOT_LIGHT_MAPS
		#else
		#define SPOT_LIGHT_MAP_INDEX ( UNROLLED_LOOP_INDEX - NUM_SPOT_LIGHT_SHADOWS + NUM_SPOT_LIGHT_SHADOWS_WITH_MAPS )
		#endif
		#if ( SPOT_LIGHT_MAP_INDEX < NUM_SPOT_LIGHT_MAPS )
			spotLightCoord = vSpotLightCoord[ i ].xyz / vSpotLightCoord[ i ].w;
			inSpotLightMap = all( lessThan( abs( spotLightCoord * 2. - 1. ), vec3( 1.0 ) ) );
			spotColor = texture2D( spotLightMap[ SPOT_LIGHT_MAP_INDEX ], spotLightCoord.xy );
			directLight.color = inSpotLightMap ? directLight.color * spotColor.rgb : directLight.color;
		#endif
		#undef SPOT_LIGHT_MAP_INDEX
		#if defined( USE_SHADOWMAP ) && ( UNROLLED_LOOP_INDEX < NUM_SPOT_LIGHT_SHADOWS )
		spotLightShadow = spotLightShadows[ i ];
		directLight.color *= ( directLight.visible && receiveShadow ) ? getShadow( spotShadowMap[ i ], spotLightShadow.shadowMapSize, spotLightShadow.shadowIntensity, spotLightShadow.shadowBias, spotLightShadow.shadowRadius, vSpotLightCoord[ i ] ) : 1.0;
		#endif
		RE_Direct( directLight, geometryPosition, geometryNormal, geometryViewDir, geometryClearcoatNormal, material, reflectedLight );
	}
	#pragma unroll_loop_end
#endif
#if ( NUM_DIR_LIGHTS > 0 ) && defined( RE_Direct )
	DirectionalLight directionalLight;
	#if defined( USE_SHADOWMAP ) && NUM_DIR_LIGHT_SHADOWS > 0
	DirectionalLightShadow directionalLightShadow;
	#endif
	#pragma unroll_loop_start
	for ( int i = 0; i < NUM_DIR_LIGHTS; i ++ ) {
		directionalLight = directionalLights[ i ];
		getDirectionalLightInfo( directionalLight, directLight );
		#if defined( USE_SHADOWMAP ) && ( UNROLLED_LOOP_INDEX < NUM_DIR_LIGHT_SHADOWS )
		directionalLightShadow = directionalLightShadows[ i ];
		directLight.color *= ( directLight.visible && receiveShadow ) ? getShadow( directionalShadowMap[ i ], directionalLightShadow.shadowMapSize, directionalLightShadow.shadowIntensity, directionalLightShadow.shadowBias, directionalLightShadow.shadowRadius, vDirectionalShadowCoord[ i ] ) : 1.0;
		#endif
		RE_Direct( directLight, geometryPosition, geometryNormal, geometryViewDir, geometryClearcoatNormal, material, reflectedLight );
	}
	#pragma unroll_loop_end
#endif
#if ( NUM_RECT_AREA_LIGHTS > 0 ) && defined( RE_Direct_RectArea )
	RectAreaLight rectAreaLight;
	#pragma unroll_loop_start
	for ( int i = 0; i < NUM_RECT_AREA_LIGHTS; i ++ ) {
		rectAreaLight = rectAreaLights[ i ];
		RE_Direct_RectArea( rectAreaLight, geometryPosition, geometryNormal, geometryViewDir, geometryClearcoatNormal, material, reflectedLight );
	}
	#pragma unroll_loop_end
#endif
#if defined( RE_IndirectDiffuse )
	vec3 iblIrradiance = vec3( 0.0 );
	vec3 irradiance = getAmbientLightIrradiance( ambientLightColor );
	#if defined( USE_LIGHT_PROBES )
		irradiance += getLightProbeIrradiance( lightProbe, geometryNormal );
	#endif
	#if ( NUM_HEMI_LIGHTS > 0 )
		#pragma unroll_loop_start
		for ( int i = 0; i < NUM_HEMI_LIGHTS; i ++ ) {
			irradiance += getHemisphereLightIrradiance( hemisphereLights[ i ], geometryNormal );
		}
		#pragma unroll_loop_end
	#endif
	#ifdef USE_LIGHT_PROBES_GRID
		vec3 probeWorldPos = ( ( vec4( geometryPosition, 1.0 ) - viewMatrix[ 3 ] ) * viewMatrix ).xyz;
		vec3 probeWorldNormal = inverseTransformDirection( geometryNormal, viewMatrix );
		irradiance += getLightProbeGridIrradiance( probeWorldPos, probeWorldNormal );
	#endif
#endif
#if defined( RE_IndirectSpecular )
	vec3 radiance = vec3( 0.0 );
	vec3 clearcoatRadiance = vec3( 0.0 );
#endif`,lights_fragment_maps:`#if defined( RE_IndirectDiffuse )
	#ifdef USE_LIGHTMAP
		vec4 lightMapTexel = texture2D( lightMap, vLightMapUv );
		vec3 lightMapIrradiance = lightMapTexel.rgb * lightMapIntensity;
		irradiance += lightMapIrradiance;
	#endif
	#if defined( USE_ENVMAP ) && defined( ENVMAP_TYPE_CUBE_UV )
		#if defined( STANDARD ) || defined( LAMBERT ) || defined( PHONG )
			iblIrradiance += getIBLIrradiance( geometryNormal );
		#endif
	#endif
#endif
#if defined( USE_ENVMAP ) && defined( RE_IndirectSpecular )
	#ifdef USE_ANISOTROPY
		radiance += getIBLAnisotropyRadiance( geometryViewDir, geometryNormal, material.roughness, material.anisotropyB, material.anisotropy );
	#else
		radiance += getIBLRadiance( geometryViewDir, geometryNormal, material.roughness );
	#endif
	#ifdef USE_CLEARCOAT
		clearcoatRadiance += getIBLRadiance( geometryViewDir, geometryClearcoatNormal, material.clearcoatRoughness );
	#endif
#endif`,lights_fragment_end:`#if defined( RE_IndirectDiffuse )
	#if defined( LAMBERT ) || defined( PHONG )
		irradiance += iblIrradiance;
	#endif
	RE_IndirectDiffuse( irradiance, geometryPosition, geometryNormal, geometryViewDir, geometryClearcoatNormal, material, reflectedLight );
#endif
#if defined( RE_IndirectSpecular )
	RE_IndirectSpecular( radiance, iblIrradiance, clearcoatRadiance, geometryPosition, geometryNormal, geometryViewDir, geometryClearcoatNormal, material, reflectedLight );
#endif`,lightprobes_pars_fragment:`#ifdef USE_LIGHT_PROBES_GRID
uniform highp sampler3D probesSH;
uniform vec3 probesMin;
uniform vec3 probesMax;
uniform vec3 probesResolution;
vec3 getLightProbeGridIrradiance( vec3 worldPos, vec3 worldNormal ) {
	vec3 res = probesResolution;
	vec3 gridRange = probesMax - probesMin;
	vec3 resMinusOne = res - 1.0;
	vec3 probeSpacing = gridRange / resMinusOne;
	vec3 samplePos = worldPos + worldNormal * probeSpacing * 0.5;
	vec3 uvw = clamp( ( samplePos - probesMin ) / gridRange, 0.0, 1.0 );
	uvw = uvw * resMinusOne / res + 0.5 / res;
	float nz          = res.z;
	float paddedSlices = nz + 2.0;
	float atlasDepth  = 7.0 * paddedSlices;
	float uvZBase     = uvw.z * nz + 1.0;
	vec4 s0 = texture( probesSH, vec3( uvw.xy, ( uvZBase                       ) / atlasDepth ) );
	vec4 s1 = texture( probesSH, vec3( uvw.xy, ( uvZBase +       paddedSlices   ) / atlasDepth ) );
	vec4 s2 = texture( probesSH, vec3( uvw.xy, ( uvZBase + 2.0 * paddedSlices   ) / atlasDepth ) );
	vec4 s3 = texture( probesSH, vec3( uvw.xy, ( uvZBase + 3.0 * paddedSlices   ) / atlasDepth ) );
	vec4 s4 = texture( probesSH, vec3( uvw.xy, ( uvZBase + 4.0 * paddedSlices   ) / atlasDepth ) );
	vec4 s5 = texture( probesSH, vec3( uvw.xy, ( uvZBase + 5.0 * paddedSlices   ) / atlasDepth ) );
	vec4 s6 = texture( probesSH, vec3( uvw.xy, ( uvZBase + 6.0 * paddedSlices   ) / atlasDepth ) );
	vec3 c0 = s0.xyz;
	vec3 c1 = vec3( s0.w, s1.xy );
	vec3 c2 = vec3( s1.zw, s2.x );
	vec3 c3 = s2.yzw;
	vec3 c4 = s3.xyz;
	vec3 c5 = vec3( s3.w, s4.xy );
	vec3 c6 = vec3( s4.zw, s5.x );
	vec3 c7 = s5.yzw;
	vec3 c8 = s6.xyz;
	float x = worldNormal.x, y = worldNormal.y, z = worldNormal.z;
	vec3 result = c0 * 0.886227;
	result += c1 * 2.0 * 0.511664 * y;
	result += c2 * 2.0 * 0.511664 * z;
	result += c3 * 2.0 * 0.511664 * x;
	result += c4 * 2.0 * 0.429043 * x * y;
	result += c5 * 2.0 * 0.429043 * y * z;
	result += c6 * ( 0.743125 * z * z - 0.247708 );
	result += c7 * 2.0 * 0.429043 * x * z;
	result += c8 * 0.429043 * ( x * x - y * y );
	return max( result, vec3( 0.0 ) );
}
#endif`,logdepthbuf_fragment:`#if defined( USE_LOGARITHMIC_DEPTH_BUFFER )
	gl_FragDepth = vIsPerspective == 0.0 ? gl_FragCoord.z : log2( vFragDepth ) * logDepthBufFC * 0.5;
#endif`,logdepthbuf_pars_fragment:`#if defined( USE_LOGARITHMIC_DEPTH_BUFFER )
	uniform float logDepthBufFC;
	varying float vFragDepth;
	varying float vIsPerspective;
#endif`,logdepthbuf_pars_vertex:`#ifdef USE_LOGARITHMIC_DEPTH_BUFFER
	varying float vFragDepth;
	varying float vIsPerspective;
#endif`,logdepthbuf_vertex:`#ifdef USE_LOGARITHMIC_DEPTH_BUFFER
	vFragDepth = 1.0 + gl_Position.w;
	vIsPerspective = float( isPerspectiveMatrix( projectionMatrix ) );
#endif`,map_fragment:`#ifdef USE_MAP
	vec4 sampledDiffuseColor = texture2D( map, vMapUv );
	#ifdef DECODE_VIDEO_TEXTURE
		sampledDiffuseColor = sRGBTransferEOTF( sampledDiffuseColor );
	#endif
	diffuseColor *= sampledDiffuseColor;
#endif`,map_pars_fragment:`#ifdef USE_MAP
	uniform sampler2D map;
#endif`,map_particle_fragment:`#if defined( USE_MAP ) || defined( USE_ALPHAMAP )
	#if defined( USE_POINTS_UV )
		vec2 uv = vUv;
	#else
		vec2 uv = ( uvTransform * vec3( gl_PointCoord.x, 1.0 - gl_PointCoord.y, 1 ) ).xy;
	#endif
#endif
#ifdef USE_MAP
	diffuseColor *= texture2D( map, uv );
#endif
#ifdef USE_ALPHAMAP
	diffuseColor.a *= texture2D( alphaMap, uv ).g;
#endif`,map_particle_pars_fragment:`#if defined( USE_POINTS_UV )
	varying vec2 vUv;
#else
	#if defined( USE_MAP ) || defined( USE_ALPHAMAP )
		uniform mat3 uvTransform;
	#endif
#endif
#ifdef USE_MAP
	uniform sampler2D map;
#endif
#ifdef USE_ALPHAMAP
	uniform sampler2D alphaMap;
#endif`,metalnessmap_fragment:`float metalnessFactor = metalness;
#ifdef USE_METALNESSMAP
	vec4 texelMetalness = texture2D( metalnessMap, vMetalnessMapUv );
	metalnessFactor *= texelMetalness.b;
#endif`,metalnessmap_pars_fragment:`#ifdef USE_METALNESSMAP
	uniform sampler2D metalnessMap;
#endif`,morphinstance_vertex:`#ifdef USE_INSTANCING_MORPH
	float morphTargetInfluences[ MORPHTARGETS_COUNT ];
	float morphTargetBaseInfluence = texelFetch( morphTexture, ivec2( 0, gl_InstanceID ), 0 ).r;
	for ( int i = 0; i < MORPHTARGETS_COUNT; i ++ ) {
		morphTargetInfluences[i] =  texelFetch( morphTexture, ivec2( i + 1, gl_InstanceID ), 0 ).r;
	}
#endif`,morphcolor_vertex:`#if defined( USE_MORPHCOLORS )
	vColor *= morphTargetBaseInfluence;
	for ( int i = 0; i < MORPHTARGETS_COUNT; i ++ ) {
		#if defined( USE_COLOR_ALPHA )
			if ( morphTargetInfluences[ i ] != 0.0 ) vColor += getMorph( gl_VertexID, i, 2 ) * morphTargetInfluences[ i ];
		#elif defined( USE_COLOR )
			if ( morphTargetInfluences[ i ] != 0.0 ) vColor += getMorph( gl_VertexID, i, 2 ).rgb * morphTargetInfluences[ i ];
		#endif
	}
#endif`,morphnormal_vertex:`#ifdef USE_MORPHNORMALS
	objectNormal *= morphTargetBaseInfluence;
	for ( int i = 0; i < MORPHTARGETS_COUNT; i ++ ) {
		if ( morphTargetInfluences[ i ] != 0.0 ) objectNormal += getMorph( gl_VertexID, i, 1 ).xyz * morphTargetInfluences[ i ];
	}
#endif`,morphtarget_pars_vertex:`#ifdef USE_MORPHTARGETS
	#ifndef USE_INSTANCING_MORPH
		uniform float morphTargetBaseInfluence;
		uniform float morphTargetInfluences[ MORPHTARGETS_COUNT ];
	#endif
	uniform sampler2DArray morphTargetsTexture;
	uniform ivec2 morphTargetsTextureSize;
	vec4 getMorph( const in int vertexIndex, const in int morphTargetIndex, const in int offset ) {
		int texelIndex = vertexIndex * MORPHTARGETS_TEXTURE_STRIDE + offset;
		int y = texelIndex / morphTargetsTextureSize.x;
		int x = texelIndex - y * morphTargetsTextureSize.x;
		ivec3 morphUV = ivec3( x, y, morphTargetIndex );
		return texelFetch( morphTargetsTexture, morphUV, 0 );
	}
#endif`,morphtarget_vertex:`#ifdef USE_MORPHTARGETS
	transformed *= morphTargetBaseInfluence;
	for ( int i = 0; i < MORPHTARGETS_COUNT; i ++ ) {
		if ( morphTargetInfluences[ i ] != 0.0 ) transformed += getMorph( gl_VertexID, i, 0 ).xyz * morphTargetInfluences[ i ];
	}
#endif`,normal_fragment_begin:`float faceDirection = gl_FrontFacing ? 1.0 : - 1.0;
#ifdef FLAT_SHADED
	vec3 fdx = dFdx( vViewPosition );
	vec3 fdy = dFdy( vViewPosition );
	vec3 normal = normalize( cross( fdx, fdy ) );
#else
	vec3 normal = normalize( vNormal );
	#ifdef DOUBLE_SIDED
		normal *= faceDirection;
	#endif
#endif
#if defined( USE_NORMALMAP_TANGENTSPACE ) || defined( USE_CLEARCOAT_NORMALMAP ) || defined( USE_ANISOTROPY )
	#ifdef USE_TANGENT
		mat3 tbn = mat3( normalize( vTangent ), normalize( vBitangent ), normal );
	#else
		mat3 tbn = getTangentFrame( - vViewPosition, normal,
		#if defined( USE_NORMALMAP )
			vNormalMapUv
		#elif defined( USE_CLEARCOAT_NORMALMAP )
			vClearcoatNormalMapUv
		#else
			vUv
		#endif
		);
	#endif
	#if defined( DOUBLE_SIDED ) && ! defined( FLAT_SHADED )
		tbn[0] *= faceDirection;
		tbn[1] *= faceDirection;
	#endif
#endif
#ifdef USE_CLEARCOAT_NORMALMAP
	#ifdef USE_TANGENT
		mat3 tbn2 = mat3( normalize( vTangent ), normalize( vBitangent ), normal );
	#else
		mat3 tbn2 = getTangentFrame( - vViewPosition, normal, vClearcoatNormalMapUv );
	#endif
	#if defined( DOUBLE_SIDED ) && ! defined( FLAT_SHADED )
		tbn2[0] *= faceDirection;
		tbn2[1] *= faceDirection;
	#endif
#endif
vec3 nonPerturbedNormal = normal;`,normal_fragment_maps:`#ifdef USE_NORMALMAP_OBJECTSPACE
	normal = texture2D( normalMap, vNormalMapUv ).xyz * 2.0 - 1.0;
	#ifdef FLIP_SIDED
		normal = - normal;
	#endif
	#ifdef DOUBLE_SIDED
		normal = normal * faceDirection;
	#endif
	normal = normalize( normalMatrix * normal );
#elif defined( USE_NORMALMAP_TANGENTSPACE )
	vec3 mapN = texture2D( normalMap, vNormalMapUv ).xyz * 2.0 - 1.0;
	#if defined( USE_PACKED_NORMALMAP )
		mapN = vec3( mapN.xy, sqrt( saturate( 1.0 - dot( mapN.xy, mapN.xy ) ) ) );
	#endif
	mapN.xy *= normalScale;
	normal = normalize( tbn * mapN );
#elif defined( USE_BUMPMAP )
	normal = perturbNormalArb( - vViewPosition, normal, dHdxy_fwd(), faceDirection );
#endif`,normal_pars_fragment:`#ifndef FLAT_SHADED
	varying vec3 vNormal;
	#ifdef USE_TANGENT
		varying vec3 vTangent;
		varying vec3 vBitangent;
	#endif
#endif`,normal_pars_vertex:`#ifndef FLAT_SHADED
	varying vec3 vNormal;
	#ifdef USE_TANGENT
		varying vec3 vTangent;
		varying vec3 vBitangent;
	#endif
#endif`,normal_vertex:`#ifndef FLAT_SHADED
	vNormal = normalize( transformedNormal );
	#ifdef USE_TANGENT
		vTangent = normalize( transformedTangent );
		vBitangent = normalize( cross( vNormal, vTangent ) * tangent.w );
	#endif
#endif`,normalmap_pars_fragment:`#ifdef USE_NORMALMAP
	uniform sampler2D normalMap;
	uniform vec2 normalScale;
#endif
#ifdef USE_NORMALMAP_OBJECTSPACE
	uniform mat3 normalMatrix;
#endif
#if ! defined ( USE_TANGENT ) && ( defined ( USE_NORMALMAP_TANGENTSPACE ) || defined ( USE_CLEARCOAT_NORMALMAP ) || defined( USE_ANISOTROPY ) )
	mat3 getTangentFrame( vec3 eye_pos, vec3 surf_norm, vec2 uv ) {
		vec3 q0 = dFdx( eye_pos.xyz );
		vec3 q1 = dFdy( eye_pos.xyz );
		vec2 st0 = dFdx( uv.st );
		vec2 st1 = dFdy( uv.st );
		vec3 N = surf_norm;
		vec3 q1perp = cross( q1, N );
		vec3 q0perp = cross( N, q0 );
		vec3 T = q1perp * st0.x + q0perp * st1.x;
		vec3 B = q1perp * st0.y + q0perp * st1.y;
		float det = max( dot( T, T ), dot( B, B ) );
		float scale = ( det == 0.0 ) ? 0.0 : inversesqrt( det );
		return mat3( T * scale, B * scale, N );
	}
#endif`,clearcoat_normal_fragment_begin:`#ifdef USE_CLEARCOAT
	vec3 clearcoatNormal = nonPerturbedNormal;
#endif`,clearcoat_normal_fragment_maps:`#ifdef USE_CLEARCOAT_NORMALMAP
	vec3 clearcoatMapN = texture2D( clearcoatNormalMap, vClearcoatNormalMapUv ).xyz * 2.0 - 1.0;
	clearcoatMapN.xy *= clearcoatNormalScale;
	clearcoatNormal = normalize( tbn2 * clearcoatMapN );
#endif`,clearcoat_pars_fragment:`#ifdef USE_CLEARCOATMAP
	uniform sampler2D clearcoatMap;
#endif
#ifdef USE_CLEARCOAT_NORMALMAP
	uniform sampler2D clearcoatNormalMap;
	uniform vec2 clearcoatNormalScale;
#endif
#ifdef USE_CLEARCOAT_ROUGHNESSMAP
	uniform sampler2D clearcoatRoughnessMap;
#endif`,iridescence_pars_fragment:`#ifdef USE_IRIDESCENCEMAP
	uniform sampler2D iridescenceMap;
#endif
#ifdef USE_IRIDESCENCE_THICKNESSMAP
	uniform sampler2D iridescenceThicknessMap;
#endif`,opaque_fragment:`#ifdef OPAQUE
diffuseColor.a = 1.0;
#endif
#ifdef USE_TRANSMISSION
diffuseColor.a *= material.transmissionAlpha;
#endif
gl_FragColor = vec4( outgoingLight, diffuseColor.a );`,packing:`vec3 packNormalToRGB( const in vec3 normal ) {
	return normalize( normal ) * 0.5 + 0.5;
}
vec3 unpackRGBToNormal( const in vec3 rgb ) {
	return 2.0 * rgb.xyz - 1.0;
}
const float PackUpscale = 256. / 255.;const float UnpackDownscale = 255. / 256.;const float ShiftRight8 = 1. / 256.;
const float Inv255 = 1. / 255.;
const vec4 PackFactors = vec4( 1.0, 256.0, 256.0 * 256.0, 256.0 * 256.0 * 256.0 );
const vec2 UnpackFactors2 = vec2( UnpackDownscale, 1.0 / PackFactors.g );
const vec3 UnpackFactors3 = vec3( UnpackDownscale / PackFactors.rg, 1.0 / PackFactors.b );
const vec4 UnpackFactors4 = vec4( UnpackDownscale / PackFactors.rgb, 1.0 / PackFactors.a );
vec4 packDepthToRGBA( const in float v ) {
	if( v <= 0.0 )
		return vec4( 0., 0., 0., 0. );
	if( v >= 1.0 )
		return vec4( 1., 1., 1., 1. );
	float vuf;
	float af = modf( v * PackFactors.a, vuf );
	float bf = modf( vuf * ShiftRight8, vuf );
	float gf = modf( vuf * ShiftRight8, vuf );
	return vec4( vuf * Inv255, gf * PackUpscale, bf * PackUpscale, af );
}
vec3 packDepthToRGB( const in float v ) {
	if( v <= 0.0 )
		return vec3( 0., 0., 0. );
	if( v >= 1.0 )
		return vec3( 1., 1., 1. );
	float vuf;
	float bf = modf( v * PackFactors.b, vuf );
	float gf = modf( vuf * ShiftRight8, vuf );
	return vec3( vuf * Inv255, gf * PackUpscale, bf );
}
vec2 packDepthToRG( const in float v ) {
	if( v <= 0.0 )
		return vec2( 0., 0. );
	if( v >= 1.0 )
		return vec2( 1., 1. );
	float vuf;
	float gf = modf( v * 256., vuf );
	return vec2( vuf * Inv255, gf );
}
float unpackRGBAToDepth( const in vec4 v ) {
	return dot( v, UnpackFactors4 );
}
float unpackRGBToDepth( const in vec3 v ) {
	return dot( v, UnpackFactors3 );
}
float unpackRGToDepth( const in vec2 v ) {
	return v.r * UnpackFactors2.r + v.g * UnpackFactors2.g;
}
vec4 pack2HalfToRGBA( const in vec2 v ) {
	vec4 r = vec4( v.x, fract( v.x * 255.0 ), v.y, fract( v.y * 255.0 ) );
	return vec4( r.x - r.y / 255.0, r.y, r.z - r.w / 255.0, r.w );
}
vec2 unpackRGBATo2Half( const in vec4 v ) {
	return vec2( v.x + ( v.y / 255.0 ), v.z + ( v.w / 255.0 ) );
}
float viewZToOrthographicDepth( const in float viewZ, const in float near, const in float far ) {
	return ( viewZ + near ) / ( near - far );
}
float orthographicDepthToViewZ( const in float depth, const in float near, const in float far ) {
	#ifdef USE_REVERSED_DEPTH_BUFFER
	
		return depth * ( far - near ) - far;
	#else
		return depth * ( near - far ) - near;
	#endif
}
float viewZToPerspectiveDepth( const in float viewZ, const in float near, const in float far ) {
	return ( ( near + viewZ ) * far ) / ( ( far - near ) * viewZ );
}
float perspectiveDepthToViewZ( const in float depth, const in float near, const in float far ) {
	
	#ifdef USE_REVERSED_DEPTH_BUFFER
		return ( near * far ) / ( ( near - far ) * depth - near );
	#else
		return ( near * far ) / ( ( far - near ) * depth - far );
	#endif
}`,premultiplied_alpha_fragment:`#ifdef PREMULTIPLIED_ALPHA
	gl_FragColor.rgb *= gl_FragColor.a;
#endif`,project_vertex:`vec4 mvPosition = vec4( transformed, 1.0 );
#ifdef USE_BATCHING
	mvPosition = batchingMatrix * mvPosition;
#endif
#ifdef USE_INSTANCING
	mvPosition = instanceMatrix * mvPosition;
#endif
mvPosition = modelViewMatrix * mvPosition;
gl_Position = projectionMatrix * mvPosition;`,dithering_fragment:`#ifdef DITHERING
	gl_FragColor.rgb = dithering( gl_FragColor.rgb );
#endif`,dithering_pars_fragment:`#ifdef DITHERING
	vec3 dithering( vec3 color ) {
		float grid_position = rand( gl_FragCoord.xy );
		vec3 dither_shift_RGB = vec3( 0.25 / 255.0, -0.25 / 255.0, 0.25 / 255.0 );
		dither_shift_RGB = mix( 2.0 * dither_shift_RGB, -2.0 * dither_shift_RGB, grid_position );
		return color + dither_shift_RGB;
	}
#endif`,roughnessmap_fragment:`float roughnessFactor = roughness;
#ifdef USE_ROUGHNESSMAP
	vec4 texelRoughness = texture2D( roughnessMap, vRoughnessMapUv );
	roughnessFactor *= texelRoughness.g;
#endif`,roughnessmap_pars_fragment:`#ifdef USE_ROUGHNESSMAP
	uniform sampler2D roughnessMap;
#endif`,shadowmap_pars_fragment:`#if NUM_SPOT_LIGHT_COORDS > 0
	varying vec4 vSpotLightCoord[ NUM_SPOT_LIGHT_COORDS ];
#endif
#if NUM_SPOT_LIGHT_MAPS > 0
	uniform sampler2D spotLightMap[ NUM_SPOT_LIGHT_MAPS ];
#endif
#ifdef USE_SHADOWMAP
	#if NUM_DIR_LIGHT_SHADOWS > 0
		#if defined( SHADOWMAP_TYPE_PCF )
			uniform sampler2DShadow directionalShadowMap[ NUM_DIR_LIGHT_SHADOWS ];
		#else
			uniform sampler2D directionalShadowMap[ NUM_DIR_LIGHT_SHADOWS ];
		#endif
		varying vec4 vDirectionalShadowCoord[ NUM_DIR_LIGHT_SHADOWS ];
		struct DirectionalLightShadow {
			float shadowIntensity;
			float shadowBias;
			float shadowNormalBias;
			float shadowRadius;
			vec2 shadowMapSize;
		};
		uniform DirectionalLightShadow directionalLightShadows[ NUM_DIR_LIGHT_SHADOWS ];
	#endif
	#if NUM_SPOT_LIGHT_SHADOWS > 0
		#if defined( SHADOWMAP_TYPE_PCF )
			uniform sampler2DShadow spotShadowMap[ NUM_SPOT_LIGHT_SHADOWS ];
		#else
			uniform sampler2D spotShadowMap[ NUM_SPOT_LIGHT_SHADOWS ];
		#endif
		struct SpotLightShadow {
			float shadowIntensity;
			float shadowBias;
			float shadowNormalBias;
			float shadowRadius;
			vec2 shadowMapSize;
		};
		uniform SpotLightShadow spotLightShadows[ NUM_SPOT_LIGHT_SHADOWS ];
	#endif
	#if NUM_POINT_LIGHT_SHADOWS > 0
		#if defined( SHADOWMAP_TYPE_PCF )
			uniform samplerCubeShadow pointShadowMap[ NUM_POINT_LIGHT_SHADOWS ];
		#elif defined( SHADOWMAP_TYPE_BASIC )
			uniform samplerCube pointShadowMap[ NUM_POINT_LIGHT_SHADOWS ];
		#endif
		varying vec4 vPointShadowCoord[ NUM_POINT_LIGHT_SHADOWS ];
		struct PointLightShadow {
			float shadowIntensity;
			float shadowBias;
			float shadowNormalBias;
			float shadowRadius;
			vec2 shadowMapSize;
			float shadowCameraNear;
			float shadowCameraFar;
		};
		uniform PointLightShadow pointLightShadows[ NUM_POINT_LIGHT_SHADOWS ];
	#endif
	#if defined( SHADOWMAP_TYPE_PCF )
		float interleavedGradientNoise( vec2 position ) {
			return fract( 52.9829189 * fract( dot( position, vec2( 0.06711056, 0.00583715 ) ) ) );
		}
		vec2 vogelDiskSample( int sampleIndex, int samplesCount, float phi ) {
			const float goldenAngle = 2.399963229728653;
			float r = sqrt( ( float( sampleIndex ) + 0.5 ) / float( samplesCount ) );
			float theta = float( sampleIndex ) * goldenAngle + phi;
			return vec2( cos( theta ), sin( theta ) ) * r;
		}
	#endif
	#if defined( SHADOWMAP_TYPE_PCF )
		float getShadow( sampler2DShadow shadowMap, vec2 shadowMapSize, float shadowIntensity, float shadowBias, float shadowRadius, vec4 shadowCoord ) {
			float shadow = 1.0;
			shadowCoord.xyz /= shadowCoord.w;
			shadowCoord.z += shadowBias;
			bool inFrustum = shadowCoord.x >= 0.0 && shadowCoord.x <= 1.0 && shadowCoord.y >= 0.0 && shadowCoord.y <= 1.0;
			bool frustumTest = inFrustum && shadowCoord.z <= 1.0;
			if ( frustumTest ) {
				vec2 texelSize = vec2( 1.0 ) / shadowMapSize;
				float radius = shadowRadius * texelSize.x;
				float phi = interleavedGradientNoise( gl_FragCoord.xy ) * PI2;
				shadow = (
					texture( shadowMap, vec3( shadowCoord.xy + vogelDiskSample( 0, 5, phi ) * radius, shadowCoord.z ) ) +
					texture( shadowMap, vec3( shadowCoord.xy + vogelDiskSample( 1, 5, phi ) * radius, shadowCoord.z ) ) +
					texture( shadowMap, vec3( shadowCoord.xy + vogelDiskSample( 2, 5, phi ) * radius, shadowCoord.z ) ) +
					texture( shadowMap, vec3( shadowCoord.xy + vogelDiskSample( 3, 5, phi ) * radius, shadowCoord.z ) ) +
					texture( shadowMap, vec3( shadowCoord.xy + vogelDiskSample( 4, 5, phi ) * radius, shadowCoord.z ) )
				) * 0.2;
			}
			return mix( 1.0, shadow, shadowIntensity );
		}
	#elif defined( SHADOWMAP_TYPE_VSM )
		float getShadow( sampler2D shadowMap, vec2 shadowMapSize, float shadowIntensity, float shadowBias, float shadowRadius, vec4 shadowCoord ) {
			float shadow = 1.0;
			shadowCoord.xyz /= shadowCoord.w;
			#ifdef USE_REVERSED_DEPTH_BUFFER
				shadowCoord.z -= shadowBias;
			#else
				shadowCoord.z += shadowBias;
			#endif
			bool inFrustum = shadowCoord.x >= 0.0 && shadowCoord.x <= 1.0 && shadowCoord.y >= 0.0 && shadowCoord.y <= 1.0;
			bool frustumTest = inFrustum && shadowCoord.z <= 1.0;
			if ( frustumTest ) {
				vec2 distribution = texture2D( shadowMap, shadowCoord.xy ).rg;
				float mean = distribution.x;
				float variance = distribution.y * distribution.y;
				#ifdef USE_REVERSED_DEPTH_BUFFER
					float hard_shadow = step( mean, shadowCoord.z );
				#else
					float hard_shadow = step( shadowCoord.z, mean );
				#endif
				
				if ( hard_shadow == 1.0 ) {
					shadow = 1.0;
				} else {
					variance = max( variance, 0.0000001 );
					float d = shadowCoord.z - mean;
					float p_max = variance / ( variance + d * d );
					p_max = clamp( ( p_max - 0.3 ) / 0.65, 0.0, 1.0 );
					shadow = max( hard_shadow, p_max );
				}
			}
			return mix( 1.0, shadow, shadowIntensity );
		}
	#else
		float getShadow( sampler2D shadowMap, vec2 shadowMapSize, float shadowIntensity, float shadowBias, float shadowRadius, vec4 shadowCoord ) {
			float shadow = 1.0;
			shadowCoord.xyz /= shadowCoord.w;
			#ifdef USE_REVERSED_DEPTH_BUFFER
				shadowCoord.z -= shadowBias;
			#else
				shadowCoord.z += shadowBias;
			#endif
			bool inFrustum = shadowCoord.x >= 0.0 && shadowCoord.x <= 1.0 && shadowCoord.y >= 0.0 && shadowCoord.y <= 1.0;
			bool frustumTest = inFrustum && shadowCoord.z <= 1.0;
			if ( frustumTest ) {
				float depth = texture2D( shadowMap, shadowCoord.xy ).r;
				#ifdef USE_REVERSED_DEPTH_BUFFER
					shadow = step( depth, shadowCoord.z );
				#else
					shadow = step( shadowCoord.z, depth );
				#endif
			}
			return mix( 1.0, shadow, shadowIntensity );
		}
	#endif
	#if NUM_POINT_LIGHT_SHADOWS > 0
	#if defined( SHADOWMAP_TYPE_PCF )
	float getPointShadow( samplerCubeShadow shadowMap, vec2 shadowMapSize, float shadowIntensity, float shadowBias, float shadowRadius, vec4 shadowCoord, float shadowCameraNear, float shadowCameraFar ) {
		float shadow = 1.0;
		vec3 lightToPosition = shadowCoord.xyz;
		vec3 bd3D = normalize( lightToPosition );
		vec3 absVec = abs( lightToPosition );
		float viewSpaceZ = max( max( absVec.x, absVec.y ), absVec.z );
		if ( viewSpaceZ - shadowCameraFar <= 0.0 && viewSpaceZ - shadowCameraNear >= 0.0 ) {
			#ifdef USE_REVERSED_DEPTH_BUFFER
				float dp = ( shadowCameraNear * ( shadowCameraFar - viewSpaceZ ) ) / ( viewSpaceZ * ( shadowCameraFar - shadowCameraNear ) );
				dp -= shadowBias;
			#else
				float dp = ( shadowCameraFar * ( viewSpaceZ - shadowCameraNear ) ) / ( viewSpaceZ * ( shadowCameraFar - shadowCameraNear ) );
				dp += shadowBias;
			#endif
			float texelSize = shadowRadius / shadowMapSize.x;
			vec3 absDir = abs( bd3D );
			vec3 tangent = absDir.x > absDir.z ? vec3( 0.0, 1.0, 0.0 ) : vec3( 1.0, 0.0, 0.0 );
			tangent = normalize( cross( bd3D, tangent ) );
			vec3 bitangent = cross( bd3D, tangent );
			float phi = interleavedGradientNoise( gl_FragCoord.xy ) * PI2;
			vec2 sample0 = vogelDiskSample( 0, 5, phi );
			vec2 sample1 = vogelDiskSample( 1, 5, phi );
			vec2 sample2 = vogelDiskSample( 2, 5, phi );
			vec2 sample3 = vogelDiskSample( 3, 5, phi );
			vec2 sample4 = vogelDiskSample( 4, 5, phi );
			shadow = (
				texture( shadowMap, vec4( bd3D + ( tangent * sample0.x + bitangent * sample0.y ) * texelSize, dp ) ) +
				texture( shadowMap, vec4( bd3D + ( tangent * sample1.x + bitangent * sample1.y ) * texelSize, dp ) ) +
				texture( shadowMap, vec4( bd3D + ( tangent * sample2.x + bitangent * sample2.y ) * texelSize, dp ) ) +
				texture( shadowMap, vec4( bd3D + ( tangent * sample3.x + bitangent * sample3.y ) * texelSize, dp ) ) +
				texture( shadowMap, vec4( bd3D + ( tangent * sample4.x + bitangent * sample4.y ) * texelSize, dp ) )
			) * 0.2;
		}
		return mix( 1.0, shadow, shadowIntensity );
	}
	#elif defined( SHADOWMAP_TYPE_BASIC )
	float getPointShadow( samplerCube shadowMap, vec2 shadowMapSize, float shadowIntensity, float shadowBias, float shadowRadius, vec4 shadowCoord, float shadowCameraNear, float shadowCameraFar ) {
		float shadow = 1.0;
		vec3 lightToPosition = shadowCoord.xyz;
		vec3 absVec = abs( lightToPosition );
		float viewSpaceZ = max( max( absVec.x, absVec.y ), absVec.z );
		if ( viewSpaceZ - shadowCameraFar <= 0.0 && viewSpaceZ - shadowCameraNear >= 0.0 ) {
			float dp = ( shadowCameraFar * ( viewSpaceZ - shadowCameraNear ) ) / ( viewSpaceZ * ( shadowCameraFar - shadowCameraNear ) );
			dp += shadowBias;
			vec3 bd3D = normalize( lightToPosition );
			float depth = textureCube( shadowMap, bd3D ).r;
			#ifdef USE_REVERSED_DEPTH_BUFFER
				depth = 1.0 - depth;
			#endif
			shadow = step( dp, depth );
		}
		return mix( 1.0, shadow, shadowIntensity );
	}
	#endif
	#endif
#endif`,shadowmap_pars_vertex:`#if NUM_SPOT_LIGHT_COORDS > 0
	uniform mat4 spotLightMatrix[ NUM_SPOT_LIGHT_COORDS ];
	varying vec4 vSpotLightCoord[ NUM_SPOT_LIGHT_COORDS ];
#endif
#ifdef USE_SHADOWMAP
	#if NUM_DIR_LIGHT_SHADOWS > 0
		uniform mat4 directionalShadowMatrix[ NUM_DIR_LIGHT_SHADOWS ];
		varying vec4 vDirectionalShadowCoord[ NUM_DIR_LIGHT_SHADOWS ];
		struct DirectionalLightShadow {
			float shadowIntensity;
			float shadowBias;
			float shadowNormalBias;
			float shadowRadius;
			vec2 shadowMapSize;
		};
		uniform DirectionalLightShadow directionalLightShadows[ NUM_DIR_LIGHT_SHADOWS ];
	#endif
	#if NUM_SPOT_LIGHT_SHADOWS > 0
		struct SpotLightShadow {
			float shadowIntensity;
			float shadowBias;
			float shadowNormalBias;
			float shadowRadius;
			vec2 shadowMapSize;
		};
		uniform SpotLightShadow spotLightShadows[ NUM_SPOT_LIGHT_SHADOWS ];
	#endif
	#if NUM_POINT_LIGHT_SHADOWS > 0
		uniform mat4 pointShadowMatrix[ NUM_POINT_LIGHT_SHADOWS ];
		varying vec4 vPointShadowCoord[ NUM_POINT_LIGHT_SHADOWS ];
		struct PointLightShadow {
			float shadowIntensity;
			float shadowBias;
			float shadowNormalBias;
			float shadowRadius;
			vec2 shadowMapSize;
			float shadowCameraNear;
			float shadowCameraFar;
		};
		uniform PointLightShadow pointLightShadows[ NUM_POINT_LIGHT_SHADOWS ];
	#endif
#endif`,shadowmap_vertex:`#if ( defined( USE_SHADOWMAP ) && ( NUM_DIR_LIGHT_SHADOWS > 0 || NUM_POINT_LIGHT_SHADOWS > 0 ) ) || ( NUM_SPOT_LIGHT_COORDS > 0 )
	#ifdef HAS_NORMAL
		vec3 shadowWorldNormal = inverseTransformDirection( transformedNormal, viewMatrix );
	#else
		vec3 shadowWorldNormal = vec3( 0.0 );
	#endif
	vec4 shadowWorldPosition;
#endif
#if defined( USE_SHADOWMAP )
	#if NUM_DIR_LIGHT_SHADOWS > 0
		#pragma unroll_loop_start
		for ( int i = 0; i < NUM_DIR_LIGHT_SHADOWS; i ++ ) {
			shadowWorldPosition = worldPosition + vec4( shadowWorldNormal * directionalLightShadows[ i ].shadowNormalBias, 0 );
			vDirectionalShadowCoord[ i ] = directionalShadowMatrix[ i ] * shadowWorldPosition;
		}
		#pragma unroll_loop_end
	#endif
	#if NUM_POINT_LIGHT_SHADOWS > 0
		#pragma unroll_loop_start
		for ( int i = 0; i < NUM_POINT_LIGHT_SHADOWS; i ++ ) {
			shadowWorldPosition = worldPosition + vec4( shadowWorldNormal * pointLightShadows[ i ].shadowNormalBias, 0 );
			vPointShadowCoord[ i ] = pointShadowMatrix[ i ] * shadowWorldPosition;
		}
		#pragma unroll_loop_end
	#endif
#endif
#if NUM_SPOT_LIGHT_COORDS > 0
	#pragma unroll_loop_start
	for ( int i = 0; i < NUM_SPOT_LIGHT_COORDS; i ++ ) {
		shadowWorldPosition = worldPosition;
		#if ( defined( USE_SHADOWMAP ) && UNROLLED_LOOP_INDEX < NUM_SPOT_LIGHT_SHADOWS )
			shadowWorldPosition.xyz += shadowWorldNormal * spotLightShadows[ i ].shadowNormalBias;
		#endif
		vSpotLightCoord[ i ] = spotLightMatrix[ i ] * shadowWorldPosition;
	}
	#pragma unroll_loop_end
#endif`,shadowmask_pars_fragment:`float getShadowMask() {
	float shadow = 1.0;
	#ifdef USE_SHADOWMAP
	#if NUM_DIR_LIGHT_SHADOWS > 0
	DirectionalLightShadow directionalLight;
	#pragma unroll_loop_start
	for ( int i = 0; i < NUM_DIR_LIGHT_SHADOWS; i ++ ) {
		directionalLight = directionalLightShadows[ i ];
		shadow *= receiveShadow ? getShadow( directionalShadowMap[ i ], directionalLight.shadowMapSize, directionalLight.shadowIntensity, directionalLight.shadowBias, directionalLight.shadowRadius, vDirectionalShadowCoord[ i ] ) : 1.0;
	}
	#pragma unroll_loop_end
	#endif
	#if NUM_SPOT_LIGHT_SHADOWS > 0
	SpotLightShadow spotLight;
	#pragma unroll_loop_start
	for ( int i = 0; i < NUM_SPOT_LIGHT_SHADOWS; i ++ ) {
		spotLight = spotLightShadows[ i ];
		shadow *= receiveShadow ? getShadow( spotShadowMap[ i ], spotLight.shadowMapSize, spotLight.shadowIntensity, spotLight.shadowBias, spotLight.shadowRadius, vSpotLightCoord[ i ] ) : 1.0;
	}
	#pragma unroll_loop_end
	#endif
	#if NUM_POINT_LIGHT_SHADOWS > 0 && ( defined( SHADOWMAP_TYPE_PCF ) || defined( SHADOWMAP_TYPE_BASIC ) )
	PointLightShadow pointLight;
	#pragma unroll_loop_start
	for ( int i = 0; i < NUM_POINT_LIGHT_SHADOWS; i ++ ) {
		pointLight = pointLightShadows[ i ];
		shadow *= receiveShadow ? getPointShadow( pointShadowMap[ i ], pointLight.shadowMapSize, pointLight.shadowIntensity, pointLight.shadowBias, pointLight.shadowRadius, vPointShadowCoord[ i ], pointLight.shadowCameraNear, pointLight.shadowCameraFar ) : 1.0;
	}
	#pragma unroll_loop_end
	#endif
	#endif
	return shadow;
}`,skinbase_vertex:`#ifdef USE_SKINNING
	mat4 boneMatX = getBoneMatrix( skinIndex.x );
	mat4 boneMatY = getBoneMatrix( skinIndex.y );
	mat4 boneMatZ = getBoneMatrix( skinIndex.z );
	mat4 boneMatW = getBoneMatrix( skinIndex.w );
#endif`,skinning_pars_vertex:`#ifdef USE_SKINNING
	uniform mat4 bindMatrix;
	uniform mat4 bindMatrixInverse;
	uniform highp sampler2D boneTexture;
	mat4 getBoneMatrix( const in float i ) {
		int size = textureSize( boneTexture, 0 ).x;
		int j = int( i ) * 4;
		int x = j % size;
		int y = j / size;
		vec4 v1 = texelFetch( boneTexture, ivec2( x, y ), 0 );
		vec4 v2 = texelFetch( boneTexture, ivec2( x + 1, y ), 0 );
		vec4 v3 = texelFetch( boneTexture, ivec2( x + 2, y ), 0 );
		vec4 v4 = texelFetch( boneTexture, ivec2( x + 3, y ), 0 );
		return mat4( v1, v2, v3, v4 );
	}
#endif`,skinning_vertex:`#ifdef USE_SKINNING
	vec4 skinVertex = bindMatrix * vec4( transformed, 1.0 );
	vec4 skinned = vec4( 0.0 );
	skinned += boneMatX * skinVertex * skinWeight.x;
	skinned += boneMatY * skinVertex * skinWeight.y;
	skinned += boneMatZ * skinVertex * skinWeight.z;
	skinned += boneMatW * skinVertex * skinWeight.w;
	transformed = ( bindMatrixInverse * skinned ).xyz;
#endif`,skinnormal_vertex:`#ifdef USE_SKINNING
	mat4 skinMatrix = mat4( 0.0 );
	skinMatrix += skinWeight.x * boneMatX;
	skinMatrix += skinWeight.y * boneMatY;
	skinMatrix += skinWeight.z * boneMatZ;
	skinMatrix += skinWeight.w * boneMatW;
	skinMatrix = bindMatrixInverse * skinMatrix * bindMatrix;
	objectNormal = vec4( skinMatrix * vec4( objectNormal, 0.0 ) ).xyz;
	#ifdef USE_TANGENT
		objectTangent = vec4( skinMatrix * vec4( objectTangent, 0.0 ) ).xyz;
	#endif
#endif`,specularmap_fragment:`float specularStrength;
#ifdef USE_SPECULARMAP
	vec4 texelSpecular = texture2D( specularMap, vSpecularMapUv );
	specularStrength = texelSpecular.r;
#else
	specularStrength = 1.0;
#endif`,specularmap_pars_fragment:`#ifdef USE_SPECULARMAP
	uniform sampler2D specularMap;
#endif`,tonemapping_fragment:`#if defined( TONE_MAPPING )
	gl_FragColor.rgb = toneMapping( gl_FragColor.rgb );
#endif`,tonemapping_pars_fragment:`#ifndef saturate
#define saturate( a ) clamp( a, 0.0, 1.0 )
#endif
uniform float toneMappingExposure;
vec3 LinearToneMapping( vec3 color ) {
	return saturate( toneMappingExposure * color );
}
vec3 ReinhardToneMapping( vec3 color ) {
	color *= toneMappingExposure;
	return saturate( color / ( vec3( 1.0 ) + color ) );
}
vec3 CineonToneMapping( vec3 color ) {
	color *= toneMappingExposure;
	color = max( vec3( 0.0 ), color - 0.004 );
	return pow( ( color * ( 6.2 * color + 0.5 ) ) / ( color * ( 6.2 * color + 1.7 ) + 0.06 ), vec3( 2.2 ) );
}
vec3 RRTAndODTFit( vec3 v ) {
	vec3 a = v * ( v + 0.0245786 ) - 0.000090537;
	vec3 b = v * ( 0.983729 * v + 0.4329510 ) + 0.238081;
	return a / b;
}
vec3 ACESFilmicToneMapping( vec3 color ) {
	const mat3 ACESInputMat = mat3(
		vec3( 0.59719, 0.07600, 0.02840 ),		vec3( 0.35458, 0.90834, 0.13383 ),
		vec3( 0.04823, 0.01566, 0.83777 )
	);
	const mat3 ACESOutputMat = mat3(
		vec3(  1.60475, -0.10208, -0.00327 ),		vec3( -0.53108,  1.10813, -0.07276 ),
		vec3( -0.07367, -0.00605,  1.07602 )
	);
	color *= toneMappingExposure / 0.6;
	color = ACESInputMat * color;
	color = RRTAndODTFit( color );
	color = ACESOutputMat * color;
	return saturate( color );
}
const mat3 LINEAR_REC2020_TO_LINEAR_SRGB = mat3(
	vec3( 1.6605, - 0.1246, - 0.0182 ),
	vec3( - 0.5876, 1.1329, - 0.1006 ),
	vec3( - 0.0728, - 0.0083, 1.1187 )
);
const mat3 LINEAR_SRGB_TO_LINEAR_REC2020 = mat3(
	vec3( 0.6274, 0.0691, 0.0164 ),
	vec3( 0.3293, 0.9195, 0.0880 ),
	vec3( 0.0433, 0.0113, 0.8956 )
);
vec3 agxDefaultContrastApprox( vec3 x ) {
	vec3 x2 = x * x;
	vec3 x4 = x2 * x2;
	return + 15.5 * x4 * x2
		- 40.14 * x4 * x
		+ 31.96 * x4
		- 6.868 * x2 * x
		+ 0.4298 * x2
		+ 0.1191 * x
		- 0.00232;
}
vec3 AgXToneMapping( vec3 color ) {
	const mat3 AgXInsetMatrix = mat3(
		vec3( 0.856627153315983, 0.137318972929847, 0.11189821299995 ),
		vec3( 0.0951212405381588, 0.761241990602591, 0.0767994186031903 ),
		vec3( 0.0482516061458583, 0.101439036467562, 0.811302368396859 )
	);
	const mat3 AgXOutsetMatrix = mat3(
		vec3( 1.1271005818144368, - 0.1413297634984383, - 0.14132976349843826 ),
		vec3( - 0.11060664309660323, 1.157823702216272, - 0.11060664309660294 ),
		vec3( - 0.016493938717834573, - 0.016493938717834257, 1.2519364065950405 )
	);
	const float AgxMinEv = - 12.47393;	const float AgxMaxEv = 4.026069;
	color *= toneMappingExposure;
	color = LINEAR_SRGB_TO_LINEAR_REC2020 * color;
	color = AgXInsetMatrix * color;
	color = max( color, 1e-10 );	color = log2( color );
	color = ( color - AgxMinEv ) / ( AgxMaxEv - AgxMinEv );
	color = clamp( color, 0.0, 1.0 );
	color = agxDefaultContrastApprox( color );
	color = AgXOutsetMatrix * color;
	color = pow( max( vec3( 0.0 ), color ), vec3( 2.2 ) );
	color = LINEAR_REC2020_TO_LINEAR_SRGB * color;
	color = clamp( color, 0.0, 1.0 );
	return color;
}
vec3 NeutralToneMapping( vec3 color ) {
	const float StartCompression = 0.8 - 0.04;
	const float Desaturation = 0.15;
	color *= toneMappingExposure;
	float x = min( color.r, min( color.g, color.b ) );
	float offset = x < 0.08 ? x - 6.25 * x * x : 0.04;
	color -= offset;
	float peak = max( color.r, max( color.g, color.b ) );
	if ( peak < StartCompression ) return color;
	float d = 1. - StartCompression;
	float newPeak = 1. - d * d / ( peak + d - StartCompression );
	color *= newPeak / peak;
	float g = 1. - 1. / ( Desaturation * ( peak - newPeak ) + 1. );
	return mix( color, vec3( newPeak ), g );
}
vec3 CustomToneMapping( vec3 color ) { return color; }`,transmission_fragment:`#ifdef USE_TRANSMISSION
	material.transmission = transmission;
	material.transmissionAlpha = 1.0;
	material.thickness = thickness;
	material.attenuationDistance = attenuationDistance;
	material.attenuationColor = attenuationColor;
	#ifdef USE_TRANSMISSIONMAP
		material.transmission *= texture2D( transmissionMap, vTransmissionMapUv ).r;
	#endif
	#ifdef USE_THICKNESSMAP
		material.thickness *= texture2D( thicknessMap, vThicknessMapUv ).g;
	#endif
	vec3 pos = vWorldPosition;
	vec3 v = normalize( cameraPosition - pos );
	vec3 n = inverseTransformDirection( normal, viewMatrix );
	vec4 transmitted = getIBLVolumeRefraction(
		n, v, material.roughness, material.diffuseContribution, material.specularColorBlended, material.specularF90,
		pos, modelMatrix, viewMatrix, projectionMatrix, material.dispersion, material.ior, material.thickness,
		material.attenuationColor, material.attenuationDistance );
	material.transmissionAlpha = mix( material.transmissionAlpha, transmitted.a, material.transmission );
	totalDiffuse = mix( totalDiffuse, transmitted.rgb, material.transmission );
#endif`,transmission_pars_fragment:`#ifdef USE_TRANSMISSION
	uniform float transmission;
	uniform float thickness;
	uniform float attenuationDistance;
	uniform vec3 attenuationColor;
	#ifdef USE_TRANSMISSIONMAP
		uniform sampler2D transmissionMap;
	#endif
	#ifdef USE_THICKNESSMAP
		uniform sampler2D thicknessMap;
	#endif
	uniform vec2 transmissionSamplerSize;
	uniform sampler2D transmissionSamplerMap;
	uniform mat4 modelMatrix;
	uniform mat4 projectionMatrix;
	varying vec3 vWorldPosition;
	float w0( float a ) {
		return ( 1.0 / 6.0 ) * ( a * ( a * ( - a + 3.0 ) - 3.0 ) + 1.0 );
	}
	float w1( float a ) {
		return ( 1.0 / 6.0 ) * ( a *  a * ( 3.0 * a - 6.0 ) + 4.0 );
	}
	float w2( float a ){
		return ( 1.0 / 6.0 ) * ( a * ( a * ( - 3.0 * a + 3.0 ) + 3.0 ) + 1.0 );
	}
	float w3( float a ) {
		return ( 1.0 / 6.0 ) * ( a * a * a );
	}
	float g0( float a ) {
		return w0( a ) + w1( a );
	}
	float g1( float a ) {
		return w2( a ) + w3( a );
	}
	float h0( float a ) {
		return - 1.0 + w1( a ) / ( w0( a ) + w1( a ) );
	}
	float h1( float a ) {
		return 1.0 + w3( a ) / ( w2( a ) + w3( a ) );
	}
	vec4 bicubic( sampler2D tex, vec2 uv, vec4 texelSize, float lod ) {
		uv = uv * texelSize.zw + 0.5;
		vec2 iuv = floor( uv );
		vec2 fuv = fract( uv );
		float g0x = g0( fuv.x );
		float g1x = g1( fuv.x );
		float h0x = h0( fuv.x );
		float h1x = h1( fuv.x );
		float h0y = h0( fuv.y );
		float h1y = h1( fuv.y );
		vec2 p0 = ( vec2( iuv.x + h0x, iuv.y + h0y ) - 0.5 ) * texelSize.xy;
		vec2 p1 = ( vec2( iuv.x + h1x, iuv.y + h0y ) - 0.5 ) * texelSize.xy;
		vec2 p2 = ( vec2( iuv.x + h0x, iuv.y + h1y ) - 0.5 ) * texelSize.xy;
		vec2 p3 = ( vec2( iuv.x + h1x, iuv.y + h1y ) - 0.5 ) * texelSize.xy;
		return g0( fuv.y ) * ( g0x * textureLod( tex, p0, lod ) + g1x * textureLod( tex, p1, lod ) ) +
			g1( fuv.y ) * ( g0x * textureLod( tex, p2, lod ) + g1x * textureLod( tex, p3, lod ) );
	}
	vec4 textureBicubic( sampler2D sampler, vec2 uv, float lod ) {
		vec2 fLodSize = vec2( textureSize( sampler, int( lod ) ) );
		vec2 cLodSize = vec2( textureSize( sampler, int( lod + 1.0 ) ) );
		vec2 fLodSizeInv = 1.0 / fLodSize;
		vec2 cLodSizeInv = 1.0 / cLodSize;
		vec4 fSample = bicubic( sampler, uv, vec4( fLodSizeInv, fLodSize ), floor( lod ) );
		vec4 cSample = bicubic( sampler, uv, vec4( cLodSizeInv, cLodSize ), ceil( lod ) );
		return mix( fSample, cSample, fract( lod ) );
	}
	vec3 getVolumeTransmissionRay( const in vec3 n, const in vec3 v, const in float thickness, const in float ior, const in mat4 modelMatrix ) {
		vec3 refractionVector = refract( - v, normalize( n ), 1.0 / ior );
		vec3 modelScale;
		modelScale.x = length( vec3( modelMatrix[ 0 ].xyz ) );
		modelScale.y = length( vec3( modelMatrix[ 1 ].xyz ) );
		modelScale.z = length( vec3( modelMatrix[ 2 ].xyz ) );
		return normalize( refractionVector ) * thickness * modelScale;
	}
	float applyIorToRoughness( const in float roughness, const in float ior ) {
		return roughness * clamp( ior * 2.0 - 2.0, 0.0, 1.0 );
	}
	vec4 getTransmissionSample( const in vec2 fragCoord, const in float roughness, const in float ior ) {
		float lod = log2( transmissionSamplerSize.x ) * applyIorToRoughness( roughness, ior );
		return textureBicubic( transmissionSamplerMap, fragCoord.xy, lod );
	}
	vec3 volumeAttenuation( const in float transmissionDistance, const in vec3 attenuationColor, const in float attenuationDistance ) {
		if ( isinf( attenuationDistance ) ) {
			return vec3( 1.0 );
		} else {
			vec3 attenuationCoefficient = -log( attenuationColor ) / attenuationDistance;
			vec3 transmittance = exp( - attenuationCoefficient * transmissionDistance );			return transmittance;
		}
	}
	vec4 getIBLVolumeRefraction( const in vec3 n, const in vec3 v, const in float roughness, const in vec3 diffuseColor,
		const in vec3 specularColor, const in float specularF90, const in vec3 position, const in mat4 modelMatrix,
		const in mat4 viewMatrix, const in mat4 projMatrix, const in float dispersion, const in float ior, const in float thickness,
		const in vec3 attenuationColor, const in float attenuationDistance ) {
		vec4 transmittedLight;
		vec3 transmittance;
		#ifdef USE_DISPERSION
			float halfSpread = ( ior - 1.0 ) * 0.025 * dispersion;
			vec3 iors = vec3( ior - halfSpread, ior, ior + halfSpread );
			for ( int i = 0; i < 3; i ++ ) {
				vec3 transmissionRay = getVolumeTransmissionRay( n, v, thickness, iors[ i ], modelMatrix );
				vec3 refractedRayExit = position + transmissionRay;
				vec4 ndcPos = projMatrix * viewMatrix * vec4( refractedRayExit, 1.0 );
				vec2 refractionCoords = ndcPos.xy / ndcPos.w;
				refractionCoords += 1.0;
				refractionCoords /= 2.0;
				vec4 transmissionSample = getTransmissionSample( refractionCoords, roughness, iors[ i ] );
				transmittedLight[ i ] = transmissionSample[ i ];
				transmittedLight.a += transmissionSample.a;
				transmittance[ i ] = diffuseColor[ i ] * volumeAttenuation( length( transmissionRay ), attenuationColor, attenuationDistance )[ i ];
			}
			transmittedLight.a /= 3.0;
		#else
			vec3 transmissionRay = getVolumeTransmissionRay( n, v, thickness, ior, modelMatrix );
			vec3 refractedRayExit = position + transmissionRay;
			vec4 ndcPos = projMatrix * viewMatrix * vec4( refractedRayExit, 1.0 );
			vec2 refractionCoords = ndcPos.xy / ndcPos.w;
			refractionCoords += 1.0;
			refractionCoords /= 2.0;
			transmittedLight = getTransmissionSample( refractionCoords, roughness, ior );
			transmittance = diffuseColor * volumeAttenuation( length( transmissionRay ), attenuationColor, attenuationDistance );
		#endif
		vec3 attenuatedColor = transmittance * transmittedLight.rgb;
		vec3 F = EnvironmentBRDF( n, v, specularColor, specularF90, roughness );
		float transmittanceFactor = ( transmittance.r + transmittance.g + transmittance.b ) / 3.0;
		return vec4( ( 1.0 - F ) * attenuatedColor, 1.0 - ( 1.0 - transmittedLight.a ) * transmittanceFactor );
	}
#endif`,uv_pars_fragment:`#if defined( USE_UV ) || defined( USE_ANISOTROPY )
	varying vec2 vUv;
#endif
#ifdef USE_MAP
	varying vec2 vMapUv;
#endif
#ifdef USE_ALPHAMAP
	varying vec2 vAlphaMapUv;
#endif
#ifdef USE_LIGHTMAP
	varying vec2 vLightMapUv;
#endif
#ifdef USE_AOMAP
	varying vec2 vAoMapUv;
#endif
#ifdef USE_BUMPMAP
	varying vec2 vBumpMapUv;
#endif
#ifdef USE_NORMALMAP
	varying vec2 vNormalMapUv;
#endif
#ifdef USE_EMISSIVEMAP
	varying vec2 vEmissiveMapUv;
#endif
#ifdef USE_METALNESSMAP
	varying vec2 vMetalnessMapUv;
#endif
#ifdef USE_ROUGHNESSMAP
	varying vec2 vRoughnessMapUv;
#endif
#ifdef USE_ANISOTROPYMAP
	varying vec2 vAnisotropyMapUv;
#endif
#ifdef USE_CLEARCOATMAP
	varying vec2 vClearcoatMapUv;
#endif
#ifdef USE_CLEARCOAT_NORMALMAP
	varying vec2 vClearcoatNormalMapUv;
#endif
#ifdef USE_CLEARCOAT_ROUGHNESSMAP
	varying vec2 vClearcoatRoughnessMapUv;
#endif
#ifdef USE_IRIDESCENCEMAP
	varying vec2 vIridescenceMapUv;
#endif
#ifdef USE_IRIDESCENCE_THICKNESSMAP
	varying vec2 vIridescenceThicknessMapUv;
#endif
#ifdef USE_SHEEN_COLORMAP
	varying vec2 vSheenColorMapUv;
#endif
#ifdef USE_SHEEN_ROUGHNESSMAP
	varying vec2 vSheenRoughnessMapUv;
#endif
#ifdef USE_SPECULARMAP
	varying vec2 vSpecularMapUv;
#endif
#ifdef USE_SPECULAR_COLORMAP
	varying vec2 vSpecularColorMapUv;
#endif
#ifdef USE_SPECULAR_INTENSITYMAP
	varying vec2 vSpecularIntensityMapUv;
#endif
#ifdef USE_TRANSMISSIONMAP
	uniform mat3 transmissionMapTransform;
	varying vec2 vTransmissionMapUv;
#endif
#ifdef USE_THICKNESSMAP
	uniform mat3 thicknessMapTransform;
	varying vec2 vThicknessMapUv;
#endif`,uv_pars_vertex:`#if defined( USE_UV ) || defined( USE_ANISOTROPY )
	varying vec2 vUv;
#endif
#ifdef USE_MAP
	uniform mat3 mapTransform;
	varying vec2 vMapUv;
#endif
#ifdef USE_ALPHAMAP
	uniform mat3 alphaMapTransform;
	varying vec2 vAlphaMapUv;
#endif
#ifdef USE_LIGHTMAP
	uniform mat3 lightMapTransform;
	varying vec2 vLightMapUv;
#endif
#ifdef USE_AOMAP
	uniform mat3 aoMapTransform;
	varying vec2 vAoMapUv;
#endif
#ifdef USE_BUMPMAP
	uniform mat3 bumpMapTransform;
	varying vec2 vBumpMapUv;
#endif
#ifdef USE_NORMALMAP
	uniform mat3 normalMapTransform;
	varying vec2 vNormalMapUv;
#endif
#ifdef USE_DISPLACEMENTMAP
	uniform mat3 displacementMapTransform;
	varying vec2 vDisplacementMapUv;
#endif
#ifdef USE_EMISSIVEMAP
	uniform mat3 emissiveMapTransform;
	varying vec2 vEmissiveMapUv;
#endif
#ifdef USE_METALNESSMAP
	uniform mat3 metalnessMapTransform;
	varying vec2 vMetalnessMapUv;
#endif
#ifdef USE_ROUGHNESSMAP
	uniform mat3 roughnessMapTransform;
	varying vec2 vRoughnessMapUv;
#endif
#ifdef USE_ANISOTROPYMAP
	uniform mat3 anisotropyMapTransform;
	varying vec2 vAnisotropyMapUv;
#endif
#ifdef USE_CLEARCOATMAP
	uniform mat3 clearcoatMapTransform;
	varying vec2 vClearcoatMapUv;
#endif
#ifdef USE_CLEARCOAT_NORMALMAP
	uniform mat3 clearcoatNormalMapTransform;
	varying vec2 vClearcoatNormalMapUv;
#endif
#ifdef USE_CLEARCOAT_ROUGHNESSMAP
	uniform mat3 clearcoatRoughnessMapTransform;
	varying vec2 vClearcoatRoughnessMapUv;
#endif
#ifdef USE_SHEEN_COLORMAP
	uniform mat3 sheenColorMapTransform;
	varying vec2 vSheenColorMapUv;
#endif
#ifdef USE_SHEEN_ROUGHNESSMAP
	uniform mat3 sheenRoughnessMapTransform;
	varying vec2 vSheenRoughnessMapUv;
#endif
#ifdef USE_IRIDESCENCEMAP
	uniform mat3 iridescenceMapTransform;
	varying vec2 vIridescenceMapUv;
#endif
#ifdef USE_IRIDESCENCE_THICKNESSMAP
	uniform mat3 iridescenceThicknessMapTransform;
	varying vec2 vIridescenceThicknessMapUv;
#endif
#ifdef USE_SPECULARMAP
	uniform mat3 specularMapTransform;
	varying vec2 vSpecularMapUv;
#endif
#ifdef USE_SPECULAR_COLORMAP
	uniform mat3 specularColorMapTransform;
	varying vec2 vSpecularColorMapUv;
#endif
#ifdef USE_SPECULAR_INTENSITYMAP
	uniform mat3 specularIntensityMapTransform;
	varying vec2 vSpecularIntensityMapUv;
#endif
#ifdef USE_TRANSMISSIONMAP
	uniform mat3 transmissionMapTransform;
	varying vec2 vTransmissionMapUv;
#endif
#ifdef USE_THICKNESSMAP
	uniform mat3 thicknessMapTransform;
	varying vec2 vThicknessMapUv;
#endif`,uv_vertex:`#if defined( USE_UV ) || defined( USE_ANISOTROPY )
	vUv = vec3( uv, 1 ).xy;
#endif
#ifdef USE_MAP
	vMapUv = ( mapTransform * vec3( MAP_UV, 1 ) ).xy;
#endif
#ifdef USE_ALPHAMAP
	vAlphaMapUv = ( alphaMapTransform * vec3( ALPHAMAP_UV, 1 ) ).xy;
#endif
#ifdef USE_LIGHTMAP
	vLightMapUv = ( lightMapTransform * vec3( LIGHTMAP_UV, 1 ) ).xy;
#endif
#ifdef USE_AOMAP
	vAoMapUv = ( aoMapTransform * vec3( AOMAP_UV, 1 ) ).xy;
#endif
#ifdef USE_BUMPMAP
	vBumpMapUv = ( bumpMapTransform * vec3( BUMPMAP_UV, 1 ) ).xy;
#endif
#ifdef USE_NORMALMAP
	vNormalMapUv = ( normalMapTransform * vec3( NORMALMAP_UV, 1 ) ).xy;
#endif
#ifdef USE_DISPLACEMENTMAP
	vDisplacementMapUv = ( displacementMapTransform * vec3( DISPLACEMENTMAP_UV, 1 ) ).xy;
#endif
#ifdef USE_EMISSIVEMAP
	vEmissiveMapUv = ( emissiveMapTransform * vec3( EMISSIVEMAP_UV, 1 ) ).xy;
#endif
#ifdef USE_METALNESSMAP
	vMetalnessMapUv = ( metalnessMapTransform * vec3( METALNESSMAP_UV, 1 ) ).xy;
#endif
#ifdef USE_ROUGHNESSMAP
	vRoughnessMapUv = ( roughnessMapTransform * vec3( ROUGHNESSMAP_UV, 1 ) ).xy;
#endif
#ifdef USE_ANISOTROPYMAP
	vAnisotropyMapUv = ( anisotropyMapTransform * vec3( ANISOTROPYMAP_UV, 1 ) ).xy;
#endif
#ifdef USE_CLEARCOATMAP
	vClearcoatMapUv = ( clearcoatMapTransform * vec3( CLEARCOATMAP_UV, 1 ) ).xy;
#endif
#ifdef USE_CLEARCOAT_NORMALMAP
	vClearcoatNormalMapUv = ( clearcoatNormalMapTransform * vec3( CLEARCOAT_NORMALMAP_UV, 1 ) ).xy;
#endif
#ifdef USE_CLEARCOAT_ROUGHNESSMAP
	vClearcoatRoughnessMapUv = ( clearcoatRoughnessMapTransform * vec3( CLEARCOAT_ROUGHNESSMAP_UV, 1 ) ).xy;
#endif
#ifdef USE_IRIDESCENCEMAP
	vIridescenceMapUv = ( iridescenceMapTransform * vec3( IRIDESCENCEMAP_UV, 1 ) ).xy;
#endif
#ifdef USE_IRIDESCENCE_THICKNESSMAP
	vIridescenceThicknessMapUv = ( iridescenceThicknessMapTransform * vec3( IRIDESCENCE_THICKNESSMAP_UV, 1 ) ).xy;
#endif
#ifdef USE_SHEEN_COLORMAP
	vSheenColorMapUv = ( sheenColorMapTransform * vec3( SHEEN_COLORMAP_UV, 1 ) ).xy;
#endif
#ifdef USE_SHEEN_ROUGHNESSMAP
	vSheenRoughnessMapUv = ( sheenRoughnessMapTransform * vec3( SHEEN_ROUGHNESSMAP_UV, 1 ) ).xy;
#endif
#ifdef USE_SPECULARMAP
	vSpecularMapUv = ( specularMapTransform * vec3( SPECULARMAP_UV, 1 ) ).xy;
#endif
#ifdef USE_SPECULAR_COLORMAP
	vSpecularColorMapUv = ( specularColorMapTransform * vec3( SPECULAR_COLORMAP_UV, 1 ) ).xy;
#endif
#ifdef USE_SPECULAR_INTENSITYMAP
	vSpecularIntensityMapUv = ( specularIntensityMapTransform * vec3( SPECULAR_INTENSITYMAP_UV, 1 ) ).xy;
#endif
#ifdef USE_TRANSMISSIONMAP
	vTransmissionMapUv = ( transmissionMapTransform * vec3( TRANSMISSIONMAP_UV, 1 ) ).xy;
#endif
#ifdef USE_THICKNESSMAP
	vThicknessMapUv = ( thicknessMapTransform * vec3( THICKNESSMAP_UV, 1 ) ).xy;
#endif`,worldpos_vertex:`#if defined( USE_ENVMAP ) || defined( DISTANCE ) || defined ( USE_SHADOWMAP ) || defined ( USE_TRANSMISSION ) || NUM_SPOT_LIGHT_COORDS > 0
	vec4 worldPosition = vec4( transformed, 1.0 );
	#ifdef USE_BATCHING
		worldPosition = batchingMatrix * worldPosition;
	#endif
	#ifdef USE_INSTANCING
		worldPosition = instanceMatrix * worldPosition;
	#endif
	worldPosition = modelMatrix * worldPosition;
#endif`,background_vert:`varying vec2 vUv;
uniform mat3 uvTransform;
void main() {
	vUv = ( uvTransform * vec3( uv, 1 ) ).xy;
	gl_Position = vec4( position.xy, 1.0, 1.0 );
}`,background_frag:`uniform sampler2D t2D;
uniform float backgroundIntensity;
varying vec2 vUv;
void main() {
	vec4 texColor = texture2D( t2D, vUv );
	#ifdef DECODE_VIDEO_TEXTURE
		texColor = vec4( mix( pow( texColor.rgb * 0.9478672986 + vec3( 0.0521327014 ), vec3( 2.4 ) ), texColor.rgb * 0.0773993808, vec3( lessThanEqual( texColor.rgb, vec3( 0.04045 ) ) ) ), texColor.w );
	#endif
	texColor.rgb *= backgroundIntensity;
	gl_FragColor = texColor;
	#include <tonemapping_fragment>
	#include <colorspace_fragment>
}`,backgroundCube_vert:`varying vec3 vWorldDirection;
#include <common>
void main() {
	vWorldDirection = transformDirection( position, modelMatrix );
	#include <begin_vertex>
	#include <project_vertex>
	gl_Position.z = gl_Position.w;
}`,backgroundCube_frag:`#ifdef ENVMAP_TYPE_CUBE
	uniform samplerCube envMap;
#elif defined( ENVMAP_TYPE_CUBE_UV )
	uniform sampler2D envMap;
#endif
uniform float backgroundBlurriness;
uniform float backgroundIntensity;
uniform mat3 backgroundRotation;
varying vec3 vWorldDirection;
#include <cube_uv_reflection_fragment>
void main() {
	#ifdef ENVMAP_TYPE_CUBE
		vec4 texColor = textureCube( envMap, backgroundRotation * vWorldDirection );
	#elif defined( ENVMAP_TYPE_CUBE_UV )
		vec4 texColor = textureCubeUV( envMap, backgroundRotation * vWorldDirection, backgroundBlurriness );
	#else
		vec4 texColor = vec4( 0.0, 0.0, 0.0, 1.0 );
	#endif
	texColor.rgb *= backgroundIntensity;
	gl_FragColor = texColor;
	#include <tonemapping_fragment>
	#include <colorspace_fragment>
}`,cube_vert:`varying vec3 vWorldDirection;
#include <common>
void main() {
	vWorldDirection = transformDirection( position, modelMatrix );
	#include <begin_vertex>
	#include <project_vertex>
	gl_Position.z = gl_Position.w;
}`,cube_frag:`uniform samplerCube tCube;
uniform float tFlip;
uniform float opacity;
varying vec3 vWorldDirection;
void main() {
	vec4 texColor = textureCube( tCube, vec3( tFlip * vWorldDirection.x, vWorldDirection.yz ) );
	gl_FragColor = texColor;
	gl_FragColor.a *= opacity;
	#include <tonemapping_fragment>
	#include <colorspace_fragment>
}`,depth_vert:`#include <common>
#include <batching_pars_vertex>
#include <uv_pars_vertex>
#include <displacementmap_pars_vertex>
#include <morphtarget_pars_vertex>
#include <skinning_pars_vertex>
#include <logdepthbuf_pars_vertex>
#include <clipping_planes_pars_vertex>
varying vec2 vHighPrecisionZW;
void main() {
	#include <uv_vertex>
	#include <batching_vertex>
	#include <skinbase_vertex>
	#include <morphinstance_vertex>
	#ifdef USE_DISPLACEMENTMAP
		#include <beginnormal_vertex>
		#include <morphnormal_vertex>
		#include <skinnormal_vertex>
	#endif
	#include <begin_vertex>
	#include <morphtarget_vertex>
	#include <skinning_vertex>
	#include <displacementmap_vertex>
	#include <project_vertex>
	#include <logdepthbuf_vertex>
	#include <clipping_planes_vertex>
	vHighPrecisionZW = gl_Position.zw;
}`,depth_frag:`#if DEPTH_PACKING == 3200
	uniform float opacity;
#endif
#include <common>
#include <packing>
#include <uv_pars_fragment>
#include <map_pars_fragment>
#include <alphamap_pars_fragment>
#include <alphatest_pars_fragment>
#include <alphahash_pars_fragment>
#include <logdepthbuf_pars_fragment>
#include <clipping_planes_pars_fragment>
varying vec2 vHighPrecisionZW;
void main() {
	vec4 diffuseColor = vec4( 1.0 );
	#include <clipping_planes_fragment>
	#if DEPTH_PACKING == 3200
		diffuseColor.a = opacity;
	#endif
	#include <map_fragment>
	#include <alphamap_fragment>
	#include <alphatest_fragment>
	#include <alphahash_fragment>
	#include <logdepthbuf_fragment>
	#ifdef USE_REVERSED_DEPTH_BUFFER
		float fragCoordZ = vHighPrecisionZW[ 0 ] / vHighPrecisionZW[ 1 ];
	#else
		float fragCoordZ = 0.5 * vHighPrecisionZW[ 0 ] / vHighPrecisionZW[ 1 ] + 0.5;
	#endif
	#if DEPTH_PACKING == 3200
		gl_FragColor = vec4( vec3( 1.0 - fragCoordZ ), opacity );
	#elif DEPTH_PACKING == 3201
		gl_FragColor = packDepthToRGBA( fragCoordZ );
	#elif DEPTH_PACKING == 3202
		gl_FragColor = vec4( packDepthToRGB( fragCoordZ ), 1.0 );
	#elif DEPTH_PACKING == 3203
		gl_FragColor = vec4( packDepthToRG( fragCoordZ ), 0.0, 1.0 );
	#endif
}`,distance_vert:`#define DISTANCE
varying vec3 vWorldPosition;
#include <common>
#include <batching_pars_vertex>
#include <uv_pars_vertex>
#include <displacementmap_pars_vertex>
#include <morphtarget_pars_vertex>
#include <skinning_pars_vertex>
#include <clipping_planes_pars_vertex>
void main() {
	#include <uv_vertex>
	#include <batching_vertex>
	#include <skinbase_vertex>
	#include <morphinstance_vertex>
	#ifdef USE_DISPLACEMENTMAP
		#include <beginnormal_vertex>
		#include <morphnormal_vertex>
		#include <skinnormal_vertex>
	#endif
	#include <begin_vertex>
	#include <morphtarget_vertex>
	#include <skinning_vertex>
	#include <displacementmap_vertex>
	#include <project_vertex>
	#include <worldpos_vertex>
	#include <clipping_planes_vertex>
	vWorldPosition = worldPosition.xyz;
}`,distance_frag:`#define DISTANCE
uniform vec3 referencePosition;
uniform float nearDistance;
uniform float farDistance;
varying vec3 vWorldPosition;
#include <common>
#include <uv_pars_fragment>
#include <map_pars_fragment>
#include <alphamap_pars_fragment>
#include <alphatest_pars_fragment>
#include <alphahash_pars_fragment>
#include <clipping_planes_pars_fragment>
void main () {
	vec4 diffuseColor = vec4( 1.0 );
	#include <clipping_planes_fragment>
	#include <map_fragment>
	#include <alphamap_fragment>
	#include <alphatest_fragment>
	#include <alphahash_fragment>
	float dist = length( vWorldPosition - referencePosition );
	dist = ( dist - nearDistance ) / ( farDistance - nearDistance );
	dist = saturate( dist );
	gl_FragColor = vec4( dist, 0.0, 0.0, 1.0 );
}`,equirect_vert:`varying vec3 vWorldDirection;
#include <common>
void main() {
	vWorldDirection = transformDirection( position, modelMatrix );
	#include <begin_vertex>
	#include <project_vertex>
}`,equirect_frag:`uniform sampler2D tEquirect;
varying vec3 vWorldDirection;
#include <common>
void main() {
	vec3 direction = normalize( vWorldDirection );
	vec2 sampleUV = equirectUv( direction );
	gl_FragColor = texture2D( tEquirect, sampleUV );
	#include <tonemapping_fragment>
	#include <colorspace_fragment>
}`,linedashed_vert:`uniform float scale;
attribute float lineDistance;
varying float vLineDistance;
#include <common>
#include <uv_pars_vertex>
#include <color_pars_vertex>
#include <fog_pars_vertex>
#include <morphtarget_pars_vertex>
#include <logdepthbuf_pars_vertex>
#include <clipping_planes_pars_vertex>
void main() {
	vLineDistance = scale * lineDistance;
	#include <uv_vertex>
	#include <color_vertex>
	#include <morphinstance_vertex>
	#include <morphcolor_vertex>
	#include <begin_vertex>
	#include <morphtarget_vertex>
	#include <project_vertex>
	#include <logdepthbuf_vertex>
	#include <clipping_planes_vertex>
	#include <fog_vertex>
}`,linedashed_frag:`uniform vec3 diffuse;
uniform float opacity;
uniform float dashSize;
uniform float totalSize;
varying float vLineDistance;
#include <common>
#include <color_pars_fragment>
#include <uv_pars_fragment>
#include <map_pars_fragment>
#include <fog_pars_fragment>
#include <logdepthbuf_pars_fragment>
#include <clipping_planes_pars_fragment>
void main() {
	vec4 diffuseColor = vec4( diffuse, opacity );
	#include <clipping_planes_fragment>
	if ( mod( vLineDistance, totalSize ) > dashSize ) {
		discard;
	}
	vec3 outgoingLight = vec3( 0.0 );
	#include <logdepthbuf_fragment>
	#include <map_fragment>
	#include <color_fragment>
	outgoingLight = diffuseColor.rgb;
	#include <opaque_fragment>
	#include <tonemapping_fragment>
	#include <colorspace_fragment>
	#include <fog_fragment>
	#include <premultiplied_alpha_fragment>
}`,meshbasic_vert:`#include <common>
#include <batching_pars_vertex>
#include <uv_pars_vertex>
#include <envmap_pars_vertex>
#include <color_pars_vertex>
#include <fog_pars_vertex>
#include <morphtarget_pars_vertex>
#include <skinning_pars_vertex>
#include <logdepthbuf_pars_vertex>
#include <clipping_planes_pars_vertex>
void main() {
	#include <uv_vertex>
	#include <color_vertex>
	#include <morphinstance_vertex>
	#include <morphcolor_vertex>
	#include <batching_vertex>
	#if defined ( USE_ENVMAP ) || defined ( USE_SKINNING )
		#include <beginnormal_vertex>
		#include <morphnormal_vertex>
		#include <skinbase_vertex>
		#include <skinnormal_vertex>
		#include <defaultnormal_vertex>
	#endif
	#include <begin_vertex>
	#include <morphtarget_vertex>
	#include <skinning_vertex>
	#include <project_vertex>
	#include <logdepthbuf_vertex>
	#include <clipping_planes_vertex>
	#include <worldpos_vertex>
	#include <envmap_vertex>
	#include <fog_vertex>
}`,meshbasic_frag:`uniform vec3 diffuse;
uniform float opacity;
#ifndef FLAT_SHADED
	varying vec3 vNormal;
#endif
#include <common>
#include <dithering_pars_fragment>
#include <color_pars_fragment>
#include <uv_pars_fragment>
#include <map_pars_fragment>
#include <alphamap_pars_fragment>
#include <alphatest_pars_fragment>
#include <alphahash_pars_fragment>
#include <aomap_pars_fragment>
#include <lightmap_pars_fragment>
#include <envmap_common_pars_fragment>
#include <envmap_pars_fragment>
#include <fog_pars_fragment>
#include <specularmap_pars_fragment>
#include <logdepthbuf_pars_fragment>
#include <clipping_planes_pars_fragment>
void main() {
	vec4 diffuseColor = vec4( diffuse, opacity );
	#include <clipping_planes_fragment>
	#include <logdepthbuf_fragment>
	#include <map_fragment>
	#include <color_fragment>
	#include <alphamap_fragment>
	#include <alphatest_fragment>
	#include <alphahash_fragment>
	#include <specularmap_fragment>
	ReflectedLight reflectedLight = ReflectedLight( vec3( 0.0 ), vec3( 0.0 ), vec3( 0.0 ), vec3( 0.0 ) );
	#ifdef USE_LIGHTMAP
		vec4 lightMapTexel = texture2D( lightMap, vLightMapUv );
		reflectedLight.indirectDiffuse += lightMapTexel.rgb * lightMapIntensity * RECIPROCAL_PI;
	#else
		reflectedLight.indirectDiffuse += vec3( 1.0 );
	#endif
	#include <aomap_fragment>
	reflectedLight.indirectDiffuse *= diffuseColor.rgb;
	vec3 outgoingLight = reflectedLight.indirectDiffuse;
	#include <envmap_fragment>
	#include <opaque_fragment>
	#include <tonemapping_fragment>
	#include <colorspace_fragment>
	#include <fog_fragment>
	#include <premultiplied_alpha_fragment>
	#include <dithering_fragment>
}`,meshlambert_vert:`#define LAMBERT
varying vec3 vViewPosition;
#include <common>
#include <batching_pars_vertex>
#include <uv_pars_vertex>
#include <displacementmap_pars_vertex>
#include <envmap_pars_vertex>
#include <color_pars_vertex>
#include <fog_pars_vertex>
#include <normal_pars_vertex>
#include <morphtarget_pars_vertex>
#include <skinning_pars_vertex>
#include <shadowmap_pars_vertex>
#include <logdepthbuf_pars_vertex>
#include <clipping_planes_pars_vertex>
void main() {
	#include <uv_vertex>
	#include <color_vertex>
	#include <morphinstance_vertex>
	#include <morphcolor_vertex>
	#include <batching_vertex>
	#include <beginnormal_vertex>
	#include <morphnormal_vertex>
	#include <skinbase_vertex>
	#include <skinnormal_vertex>
	#include <defaultnormal_vertex>
	#include <normal_vertex>
	#include <begin_vertex>
	#include <morphtarget_vertex>
	#include <skinning_vertex>
	#include <displacementmap_vertex>
	#include <project_vertex>
	#include <logdepthbuf_vertex>
	#include <clipping_planes_vertex>
	vViewPosition = - mvPosition.xyz;
	#include <worldpos_vertex>
	#include <envmap_vertex>
	#include <shadowmap_vertex>
	#include <fog_vertex>
}`,meshlambert_frag:`#define LAMBERT
uniform vec3 diffuse;
uniform vec3 emissive;
uniform float opacity;
#include <common>
#include <dithering_pars_fragment>
#include <color_pars_fragment>
#include <uv_pars_fragment>
#include <map_pars_fragment>
#include <alphamap_pars_fragment>
#include <alphatest_pars_fragment>
#include <alphahash_pars_fragment>
#include <aomap_pars_fragment>
#include <lightmap_pars_fragment>
#include <emissivemap_pars_fragment>
#include <cube_uv_reflection_fragment>
#include <envmap_common_pars_fragment>
#include <envmap_pars_fragment>
#include <envmap_physical_pars_fragment>
#include <fog_pars_fragment>
#include <bsdfs>
#include <lights_pars_begin>
#include <normal_pars_fragment>
#include <lights_lambert_pars_fragment>
#include <shadowmap_pars_fragment>
#include <bumpmap_pars_fragment>
#include <normalmap_pars_fragment>
#include <specularmap_pars_fragment>
#include <logdepthbuf_pars_fragment>
#include <clipping_planes_pars_fragment>
void main() {
	vec4 diffuseColor = vec4( diffuse, opacity );
	#include <clipping_planes_fragment>
	ReflectedLight reflectedLight = ReflectedLight( vec3( 0.0 ), vec3( 0.0 ), vec3( 0.0 ), vec3( 0.0 ) );
	vec3 totalEmissiveRadiance = emissive;
	#include <logdepthbuf_fragment>
	#include <map_fragment>
	#include <color_fragment>
	#include <alphamap_fragment>
	#include <alphatest_fragment>
	#include <alphahash_fragment>
	#include <specularmap_fragment>
	#include <normal_fragment_begin>
	#include <normal_fragment_maps>
	#include <emissivemap_fragment>
	#include <lights_lambert_fragment>
	#include <lights_fragment_begin>
	#include <lights_fragment_maps>
	#include <lights_fragment_end>
	#include <aomap_fragment>
	vec3 outgoingLight = reflectedLight.directDiffuse + reflectedLight.indirectDiffuse + totalEmissiveRadiance;
	#include <envmap_fragment>
	#include <opaque_fragment>
	#include <tonemapping_fragment>
	#include <colorspace_fragment>
	#include <fog_fragment>
	#include <premultiplied_alpha_fragment>
	#include <dithering_fragment>
}`,meshmatcap_vert:`#define MATCAP
varying vec3 vViewPosition;
#include <common>
#include <batching_pars_vertex>
#include <uv_pars_vertex>
#include <color_pars_vertex>
#include <displacementmap_pars_vertex>
#include <fog_pars_vertex>
#include <normal_pars_vertex>
#include <morphtarget_pars_vertex>
#include <skinning_pars_vertex>
#include <logdepthbuf_pars_vertex>
#include <clipping_planes_pars_vertex>
void main() {
	#include <uv_vertex>
	#include <color_vertex>
	#include <morphinstance_vertex>
	#include <morphcolor_vertex>
	#include <batching_vertex>
	#include <beginnormal_vertex>
	#include <morphnormal_vertex>
	#include <skinbase_vertex>
	#include <skinnormal_vertex>
	#include <defaultnormal_vertex>
	#include <normal_vertex>
	#include <begin_vertex>
	#include <morphtarget_vertex>
	#include <skinning_vertex>
	#include <displacementmap_vertex>
	#include <project_vertex>
	#include <logdepthbuf_vertex>
	#include <clipping_planes_vertex>
	#include <fog_vertex>
	vViewPosition = - mvPosition.xyz;
}`,meshmatcap_frag:`#define MATCAP
uniform vec3 diffuse;
uniform float opacity;
uniform sampler2D matcap;
varying vec3 vViewPosition;
#include <common>
#include <dithering_pars_fragment>
#include <color_pars_fragment>
#include <uv_pars_fragment>
#include <map_pars_fragment>
#include <alphamap_pars_fragment>
#include <alphatest_pars_fragment>
#include <alphahash_pars_fragment>
#include <fog_pars_fragment>
#include <normal_pars_fragment>
#include <bumpmap_pars_fragment>
#include <normalmap_pars_fragment>
#include <logdepthbuf_pars_fragment>
#include <clipping_planes_pars_fragment>
void main() {
	vec4 diffuseColor = vec4( diffuse, opacity );
	#include <clipping_planes_fragment>
	#include <logdepthbuf_fragment>
	#include <map_fragment>
	#include <color_fragment>
	#include <alphamap_fragment>
	#include <alphatest_fragment>
	#include <alphahash_fragment>
	#include <normal_fragment_begin>
	#include <normal_fragment_maps>
	vec3 viewDir = normalize( vViewPosition );
	vec3 x = normalize( vec3( viewDir.z, 0.0, - viewDir.x ) );
	vec3 y = cross( viewDir, x );
	vec2 uv = vec2( dot( x, normal ), dot( y, normal ) ) * 0.495 + 0.5;
	#ifdef USE_MATCAP
		vec4 matcapColor = texture2D( matcap, uv );
	#else
		vec4 matcapColor = vec4( vec3( mix( 0.2, 0.8, uv.y ) ), 1.0 );
	#endif
	vec3 outgoingLight = diffuseColor.rgb * matcapColor.rgb;
	#include <opaque_fragment>
	#include <tonemapping_fragment>
	#include <colorspace_fragment>
	#include <fog_fragment>
	#include <premultiplied_alpha_fragment>
	#include <dithering_fragment>
}`,meshnormal_vert:`#define NORMAL
#if defined( FLAT_SHADED ) || defined( USE_BUMPMAP ) || defined( USE_NORMALMAP_TANGENTSPACE )
	varying vec3 vViewPosition;
#endif
#include <common>
#include <batching_pars_vertex>
#include <uv_pars_vertex>
#include <displacementmap_pars_vertex>
#include <normal_pars_vertex>
#include <morphtarget_pars_vertex>
#include <skinning_pars_vertex>
#include <logdepthbuf_pars_vertex>
#include <clipping_planes_pars_vertex>
void main() {
	#include <uv_vertex>
	#include <batching_vertex>
	#include <beginnormal_vertex>
	#include <morphinstance_vertex>
	#include <morphnormal_vertex>
	#include <skinbase_vertex>
	#include <skinnormal_vertex>
	#include <defaultnormal_vertex>
	#include <normal_vertex>
	#include <begin_vertex>
	#include <morphtarget_vertex>
	#include <skinning_vertex>
	#include <displacementmap_vertex>
	#include <project_vertex>
	#include <logdepthbuf_vertex>
	#include <clipping_planes_vertex>
#if defined( FLAT_SHADED ) || defined( USE_BUMPMAP ) || defined( USE_NORMALMAP_TANGENTSPACE )
	vViewPosition = - mvPosition.xyz;
#endif
}`,meshnormal_frag:`#define NORMAL
uniform float opacity;
#if defined( FLAT_SHADED ) || defined( USE_BUMPMAP ) || defined( USE_NORMALMAP_TANGENTSPACE )
	varying vec3 vViewPosition;
#endif
#include <uv_pars_fragment>
#include <normal_pars_fragment>
#include <bumpmap_pars_fragment>
#include <normalmap_pars_fragment>
#include <logdepthbuf_pars_fragment>
#include <clipping_planes_pars_fragment>
void main() {
	vec4 diffuseColor = vec4( 0.0, 0.0, 0.0, opacity );
	#include <clipping_planes_fragment>
	#include <logdepthbuf_fragment>
	#include <normal_fragment_begin>
	#include <normal_fragment_maps>
	gl_FragColor = vec4( normalize( normal ) * 0.5 + 0.5, diffuseColor.a );
	#ifdef OPAQUE
		gl_FragColor.a = 1.0;
	#endif
}`,meshphong_vert:`#define PHONG
varying vec3 vViewPosition;
#include <common>
#include <batching_pars_vertex>
#include <uv_pars_vertex>
#include <displacementmap_pars_vertex>
#include <envmap_pars_vertex>
#include <color_pars_vertex>
#include <fog_pars_vertex>
#include <normal_pars_vertex>
#include <morphtarget_pars_vertex>
#include <skinning_pars_vertex>
#include <shadowmap_pars_vertex>
#include <logdepthbuf_pars_vertex>
#include <clipping_planes_pars_vertex>
void main() {
	#include <uv_vertex>
	#include <color_vertex>
	#include <morphcolor_vertex>
	#include <batching_vertex>
	#include <beginnormal_vertex>
	#include <morphinstance_vertex>
	#include <morphnormal_vertex>
	#include <skinbase_vertex>
	#include <skinnormal_vertex>
	#include <defaultnormal_vertex>
	#include <normal_vertex>
	#include <begin_vertex>
	#include <morphtarget_vertex>
	#include <skinning_vertex>
	#include <displacementmap_vertex>
	#include <project_vertex>
	#include <logdepthbuf_vertex>
	#include <clipping_planes_vertex>
	vViewPosition = - mvPosition.xyz;
	#include <worldpos_vertex>
	#include <envmap_vertex>
	#include <shadowmap_vertex>
	#include <fog_vertex>
}`,meshphong_frag:`#define PHONG
uniform vec3 diffuse;
uniform vec3 emissive;
uniform vec3 specular;
uniform float shininess;
uniform float opacity;
#include <common>
#include <dithering_pars_fragment>
#include <color_pars_fragment>
#include <uv_pars_fragment>
#include <map_pars_fragment>
#include <alphamap_pars_fragment>
#include <alphatest_pars_fragment>
#include <alphahash_pars_fragment>
#include <aomap_pars_fragment>
#include <lightmap_pars_fragment>
#include <emissivemap_pars_fragment>
#include <cube_uv_reflection_fragment>
#include <envmap_common_pars_fragment>
#include <envmap_pars_fragment>
#include <envmap_physical_pars_fragment>
#include <fog_pars_fragment>
#include <bsdfs>
#include <lights_pars_begin>
#include <normal_pars_fragment>
#include <lights_phong_pars_fragment>
#include <shadowmap_pars_fragment>
#include <bumpmap_pars_fragment>
#include <normalmap_pars_fragment>
#include <specularmap_pars_fragment>
#include <logdepthbuf_pars_fragment>
#include <clipping_planes_pars_fragment>
void main() {
	vec4 diffuseColor = vec4( diffuse, opacity );
	#include <clipping_planes_fragment>
	ReflectedLight reflectedLight = ReflectedLight( vec3( 0.0 ), vec3( 0.0 ), vec3( 0.0 ), vec3( 0.0 ) );
	vec3 totalEmissiveRadiance = emissive;
	#include <logdepthbuf_fragment>
	#include <map_fragment>
	#include <color_fragment>
	#include <alphamap_fragment>
	#include <alphatest_fragment>
	#include <alphahash_fragment>
	#include <specularmap_fragment>
	#include <normal_fragment_begin>
	#include <normal_fragment_maps>
	#include <emissivemap_fragment>
	#include <lights_phong_fragment>
	#include <lights_fragment_begin>
	#include <lights_fragment_maps>
	#include <lights_fragment_end>
	#include <aomap_fragment>
	vec3 outgoingLight = reflectedLight.directDiffuse + reflectedLight.indirectDiffuse + reflectedLight.directSpecular + reflectedLight.indirectSpecular + totalEmissiveRadiance;
	#include <envmap_fragment>
	#include <opaque_fragment>
	#include <tonemapping_fragment>
	#include <colorspace_fragment>
	#include <fog_fragment>
	#include <premultiplied_alpha_fragment>
	#include <dithering_fragment>
}`,meshphysical_vert:`#define STANDARD
varying vec3 vViewPosition;
#ifdef USE_TRANSMISSION
	varying vec3 vWorldPosition;
#endif
#include <common>
#include <batching_pars_vertex>
#include <uv_pars_vertex>
#include <displacementmap_pars_vertex>
#include <color_pars_vertex>
#include <fog_pars_vertex>
#include <normal_pars_vertex>
#include <morphtarget_pars_vertex>
#include <skinning_pars_vertex>
#include <shadowmap_pars_vertex>
#include <logdepthbuf_pars_vertex>
#include <clipping_planes_pars_vertex>
void main() {
	#include <uv_vertex>
	#include <color_vertex>
	#include <morphinstance_vertex>
	#include <morphcolor_vertex>
	#include <batching_vertex>
	#include <beginnormal_vertex>
	#include <morphnormal_vertex>
	#include <skinbase_vertex>
	#include <skinnormal_vertex>
	#include <defaultnormal_vertex>
	#include <normal_vertex>
	#include <begin_vertex>
	#include <morphtarget_vertex>
	#include <skinning_vertex>
	#include <displacementmap_vertex>
	#include <project_vertex>
	#include <logdepthbuf_vertex>
	#include <clipping_planes_vertex>
	vViewPosition = - mvPosition.xyz;
	#include <worldpos_vertex>
	#include <shadowmap_vertex>
	#include <fog_vertex>
#ifdef USE_TRANSMISSION
	vWorldPosition = worldPosition.xyz;
#endif
}`,meshphysical_frag:`#define STANDARD
#ifdef PHYSICAL
	#define IOR
	#define USE_SPECULAR
#endif
uniform vec3 diffuse;
uniform vec3 emissive;
uniform float roughness;
uniform float metalness;
uniform float opacity;
#ifdef IOR
	uniform float ior;
#endif
#ifdef USE_SPECULAR
	uniform float specularIntensity;
	uniform vec3 specularColor;
	#ifdef USE_SPECULAR_COLORMAP
		uniform sampler2D specularColorMap;
	#endif
	#ifdef USE_SPECULAR_INTENSITYMAP
		uniform sampler2D specularIntensityMap;
	#endif
#endif
#ifdef USE_CLEARCOAT
	uniform float clearcoat;
	uniform float clearcoatRoughness;
#endif
#ifdef USE_DISPERSION
	uniform float dispersion;
#endif
#ifdef USE_IRIDESCENCE
	uniform float iridescence;
	uniform float iridescenceIOR;
	uniform float iridescenceThicknessMinimum;
	uniform float iridescenceThicknessMaximum;
#endif
#ifdef USE_SHEEN
	uniform vec3 sheenColor;
	uniform float sheenRoughness;
	#ifdef USE_SHEEN_COLORMAP
		uniform sampler2D sheenColorMap;
	#endif
	#ifdef USE_SHEEN_ROUGHNESSMAP
		uniform sampler2D sheenRoughnessMap;
	#endif
#endif
#ifdef USE_ANISOTROPY
	uniform vec2 anisotropyVector;
	#ifdef USE_ANISOTROPYMAP
		uniform sampler2D anisotropyMap;
	#endif
#endif
varying vec3 vViewPosition;
#include <common>
#include <dithering_pars_fragment>
#include <color_pars_fragment>
#include <uv_pars_fragment>
#include <map_pars_fragment>
#include <alphamap_pars_fragment>
#include <alphatest_pars_fragment>
#include <alphahash_pars_fragment>
#include <aomap_pars_fragment>
#include <lightmap_pars_fragment>
#include <emissivemap_pars_fragment>
#include <iridescence_fragment>
#include <cube_uv_reflection_fragment>
#include <envmap_common_pars_fragment>
#include <envmap_physical_pars_fragment>
#include <fog_pars_fragment>
#include <lights_pars_begin>
#include <normal_pars_fragment>
#include <lights_physical_pars_fragment>
#include <transmission_pars_fragment>
#include <shadowmap_pars_fragment>
#include <bumpmap_pars_fragment>
#include <normalmap_pars_fragment>
#include <clearcoat_pars_fragment>
#include <iridescence_pars_fragment>
#include <roughnessmap_pars_fragment>
#include <metalnessmap_pars_fragment>
#include <logdepthbuf_pars_fragment>
#include <clipping_planes_pars_fragment>
void main() {
	vec4 diffuseColor = vec4( diffuse, opacity );
	#include <clipping_planes_fragment>
	ReflectedLight reflectedLight = ReflectedLight( vec3( 0.0 ), vec3( 0.0 ), vec3( 0.0 ), vec3( 0.0 ) );
	vec3 totalEmissiveRadiance = emissive;
	#include <logdepthbuf_fragment>
	#include <map_fragment>
	#include <color_fragment>
	#include <alphamap_fragment>
	#include <alphatest_fragment>
	#include <alphahash_fragment>
	#include <roughnessmap_fragment>
	#include <metalnessmap_fragment>
	#include <normal_fragment_begin>
	#include <normal_fragment_maps>
	#include <clearcoat_normal_fragment_begin>
	#include <clearcoat_normal_fragment_maps>
	#include <emissivemap_fragment>
	#include <lights_physical_fragment>
	#include <lights_fragment_begin>
	#include <lights_fragment_maps>
	#include <lights_fragment_end>
	#include <aomap_fragment>
	vec3 totalDiffuse = reflectedLight.directDiffuse + reflectedLight.indirectDiffuse;
	vec3 totalSpecular = reflectedLight.directSpecular + reflectedLight.indirectSpecular;
	#include <transmission_fragment>
	vec3 outgoingLight = totalDiffuse + totalSpecular + totalEmissiveRadiance;
	#ifdef USE_SHEEN
 
		outgoingLight = outgoingLight + sheenSpecularDirect + sheenSpecularIndirect;
 
 	#endif
	#ifdef USE_CLEARCOAT
		float dotNVcc = saturate( dot( geometryClearcoatNormal, geometryViewDir ) );
		vec3 Fcc = F_Schlick( material.clearcoatF0, material.clearcoatF90, dotNVcc );
		outgoingLight = outgoingLight * ( 1.0 - material.clearcoat * Fcc ) + ( clearcoatSpecularDirect + clearcoatSpecularIndirect ) * material.clearcoat;
	#endif
	#include <opaque_fragment>
	#include <tonemapping_fragment>
	#include <colorspace_fragment>
	#include <fog_fragment>
	#include <premultiplied_alpha_fragment>
	#include <dithering_fragment>
}`,meshtoon_vert:`#define TOON
varying vec3 vViewPosition;
#include <common>
#include <batching_pars_vertex>
#include <uv_pars_vertex>
#include <displacementmap_pars_vertex>
#include <color_pars_vertex>
#include <fog_pars_vertex>
#include <normal_pars_vertex>
#include <morphtarget_pars_vertex>
#include <skinning_pars_vertex>
#include <shadowmap_pars_vertex>
#include <logdepthbuf_pars_vertex>
#include <clipping_planes_pars_vertex>
void main() {
	#include <uv_vertex>
	#include <color_vertex>
	#include <morphinstance_vertex>
	#include <morphcolor_vertex>
	#include <batching_vertex>
	#include <beginnormal_vertex>
	#include <morphnormal_vertex>
	#include <skinbase_vertex>
	#include <skinnormal_vertex>
	#include <defaultnormal_vertex>
	#include <normal_vertex>
	#include <begin_vertex>
	#include <morphtarget_vertex>
	#include <skinning_vertex>
	#include <displacementmap_vertex>
	#include <project_vertex>
	#include <logdepthbuf_vertex>
	#include <clipping_planes_vertex>
	vViewPosition = - mvPosition.xyz;
	#include <worldpos_vertex>
	#include <shadowmap_vertex>
	#include <fog_vertex>
}`,meshtoon_frag:`#define TOON
uniform vec3 diffuse;
uniform vec3 emissive;
uniform float opacity;
#include <common>
#include <dithering_pars_fragment>
#include <color_pars_fragment>
#include <uv_pars_fragment>
#include <map_pars_fragment>
#include <alphamap_pars_fragment>
#include <alphatest_pars_fragment>
#include <alphahash_pars_fragment>
#include <aomap_pars_fragment>
#include <lightmap_pars_fragment>
#include <emissivemap_pars_fragment>
#include <gradientmap_pars_fragment>
#include <fog_pars_fragment>
#include <bsdfs>
#include <lights_pars_begin>
#include <normal_pars_fragment>
#include <lights_toon_pars_fragment>
#include <shadowmap_pars_fragment>
#include <bumpmap_pars_fragment>
#include <normalmap_pars_fragment>
#include <logdepthbuf_pars_fragment>
#include <clipping_planes_pars_fragment>
void main() {
	vec4 diffuseColor = vec4( diffuse, opacity );
	#include <clipping_planes_fragment>
	ReflectedLight reflectedLight = ReflectedLight( vec3( 0.0 ), vec3( 0.0 ), vec3( 0.0 ), vec3( 0.0 ) );
	vec3 totalEmissiveRadiance = emissive;
	#include <logdepthbuf_fragment>
	#include <map_fragment>
	#include <color_fragment>
	#include <alphamap_fragment>
	#include <alphatest_fragment>
	#include <alphahash_fragment>
	#include <normal_fragment_begin>
	#include <normal_fragment_maps>
	#include <emissivemap_fragment>
	#include <lights_toon_fragment>
	#include <lights_fragment_begin>
	#include <lights_fragment_maps>
	#include <lights_fragment_end>
	#include <aomap_fragment>
	vec3 outgoingLight = reflectedLight.directDiffuse + reflectedLight.indirectDiffuse + totalEmissiveRadiance;
	#include <opaque_fragment>
	#include <tonemapping_fragment>
	#include <colorspace_fragment>
	#include <fog_fragment>
	#include <premultiplied_alpha_fragment>
	#include <dithering_fragment>
}`,points_vert:`uniform float size;
uniform float scale;
#include <common>
#include <color_pars_vertex>
#include <fog_pars_vertex>
#include <morphtarget_pars_vertex>
#include <logdepthbuf_pars_vertex>
#include <clipping_planes_pars_vertex>
#ifdef USE_POINTS_UV
	varying vec2 vUv;
	uniform mat3 uvTransform;
#endif
void main() {
	#ifdef USE_POINTS_UV
		vUv = ( uvTransform * vec3( uv, 1 ) ).xy;
	#endif
	#include <color_vertex>
	#include <morphinstance_vertex>
	#include <morphcolor_vertex>
	#include <begin_vertex>
	#include <morphtarget_vertex>
	#include <project_vertex>
	gl_PointSize = size;
	#ifdef USE_SIZEATTENUATION
		bool isPerspective = isPerspectiveMatrix( projectionMatrix );
		if ( isPerspective ) gl_PointSize *= ( scale / - mvPosition.z );
	#endif
	#include <logdepthbuf_vertex>
	#include <clipping_planes_vertex>
	#include <worldpos_vertex>
	#include <fog_vertex>
}`,points_frag:`uniform vec3 diffuse;
uniform float opacity;
#include <common>
#include <color_pars_fragment>
#include <map_particle_pars_fragment>
#include <alphatest_pars_fragment>
#include <alphahash_pars_fragment>
#include <fog_pars_fragment>
#include <logdepthbuf_pars_fragment>
#include <clipping_planes_pars_fragment>
void main() {
	vec4 diffuseColor = vec4( diffuse, opacity );
	#include <clipping_planes_fragment>
	vec3 outgoingLight = vec3( 0.0 );
	#include <logdepthbuf_fragment>
	#include <map_particle_fragment>
	#include <color_fragment>
	#include <alphatest_fragment>
	#include <alphahash_fragment>
	outgoingLight = diffuseColor.rgb;
	#include <opaque_fragment>
	#include <tonemapping_fragment>
	#include <colorspace_fragment>
	#include <fog_fragment>
	#include <premultiplied_alpha_fragment>
}`,shadow_vert:`#include <common>
#include <batching_pars_vertex>
#include <fog_pars_vertex>
#include <morphtarget_pars_vertex>
#include <skinning_pars_vertex>
#include <logdepthbuf_pars_vertex>
#include <shadowmap_pars_vertex>
void main() {
	#include <batching_vertex>
	#include <beginnormal_vertex>
	#include <morphinstance_vertex>
	#include <morphnormal_vertex>
	#include <skinbase_vertex>
	#include <skinnormal_vertex>
	#include <defaultnormal_vertex>
	#include <begin_vertex>
	#include <morphtarget_vertex>
	#include <skinning_vertex>
	#include <project_vertex>
	#include <logdepthbuf_vertex>
	#include <worldpos_vertex>
	#include <shadowmap_vertex>
	#include <fog_vertex>
}`,shadow_frag:`uniform vec3 color;
uniform float opacity;
#include <common>
#include <fog_pars_fragment>
#include <bsdfs>
#include <lights_pars_begin>
#include <logdepthbuf_pars_fragment>
#include <shadowmap_pars_fragment>
#include <shadowmask_pars_fragment>
void main() {
	#include <logdepthbuf_fragment>
	gl_FragColor = vec4( color, opacity * ( 1.0 - getShadowMask() ) );
	#include <tonemapping_fragment>
	#include <colorspace_fragment>
	#include <fog_fragment>
	#include <premultiplied_alpha_fragment>
}`,sprite_vert:`uniform float rotation;
uniform vec2 center;
#include <common>
#include <uv_pars_vertex>
#include <fog_pars_vertex>
#include <logdepthbuf_pars_vertex>
#include <clipping_planes_pars_vertex>
void main() {
	#include <uv_vertex>
	vec4 mvPosition = modelViewMatrix[ 3 ];
	vec2 scale = vec2( length( modelMatrix[ 0 ].xyz ), length( modelMatrix[ 1 ].xyz ) );
	#ifndef USE_SIZEATTENUATION
		bool isPerspective = isPerspectiveMatrix( projectionMatrix );
		if ( isPerspective ) scale *= - mvPosition.z;
	#endif
	vec2 alignedPosition = ( position.xy - ( center - vec2( 0.5 ) ) ) * scale;
	vec2 rotatedPosition;
	rotatedPosition.x = cos( rotation ) * alignedPosition.x - sin( rotation ) * alignedPosition.y;
	rotatedPosition.y = sin( rotation ) * alignedPosition.x + cos( rotation ) * alignedPosition.y;
	mvPosition.xy += rotatedPosition;
	gl_Position = projectionMatrix * mvPosition;
	#include <logdepthbuf_vertex>
	#include <clipping_planes_vertex>
	#include <fog_vertex>
}`,sprite_frag:`uniform vec3 diffuse;
uniform float opacity;
#include <common>
#include <uv_pars_fragment>
#include <map_pars_fragment>
#include <alphamap_pars_fragment>
#include <alphatest_pars_fragment>
#include <alphahash_pars_fragment>
#include <fog_pars_fragment>
#include <logdepthbuf_pars_fragment>
#include <clipping_planes_pars_fragment>
void main() {
	vec4 diffuseColor = vec4( diffuse, opacity );
	#include <clipping_planes_fragment>
	vec3 outgoingLight = vec3( 0.0 );
	#include <logdepthbuf_fragment>
	#include <map_fragment>
	#include <alphamap_fragment>
	#include <alphatest_fragment>
	#include <alphahash_fragment>
	outgoingLight = diffuseColor.rgb;
	#include <opaque_fragment>
	#include <tonemapping_fragment>
	#include <colorspace_fragment>
	#include <fog_fragment>
}`},q={common:{diffuse:{value:new W(16777215)},opacity:{value:1},map:{value:null},mapTransform:{value:new U},alphaMap:{value:null},alphaMapTransform:{value:new U},alphaTest:{value:0}},specularmap:{specularMap:{value:null},specularMapTransform:{value:new U}},envmap:{envMap:{value:null},envMapRotation:{value:new U},reflectivity:{value:1},ior:{value:1.5},refractionRatio:{value:.98},dfgLUT:{value:null}},aomap:{aoMap:{value:null},aoMapIntensity:{value:1},aoMapTransform:{value:new U}},lightmap:{lightMap:{value:null},lightMapIntensity:{value:1},lightMapTransform:{value:new U}},bumpmap:{bumpMap:{value:null},bumpMapTransform:{value:new U},bumpScale:{value:1}},normalmap:{normalMap:{value:null},normalMapTransform:{value:new U},normalScale:{value:new V(1,1)}},displacementmap:{displacementMap:{value:null},displacementMapTransform:{value:new U},displacementScale:{value:1},displacementBias:{value:0}},emissivemap:{emissiveMap:{value:null},emissiveMapTransform:{value:new U}},metalnessmap:{metalnessMap:{value:null},metalnessMapTransform:{value:new U}},roughnessmap:{roughnessMap:{value:null},roughnessMapTransform:{value:new U}},gradientmap:{gradientMap:{value:null}},fog:{fogDensity:{value:25e-5},fogNear:{value:1},fogFar:{value:2e3},fogColor:{value:new W(16777215)}},lights:{ambientLightColor:{value:[]},lightProbe:{value:[]},directionalLights:{value:[],properties:{direction:{},color:{}}},directionalLightShadows:{value:[],properties:{shadowIntensity:1,shadowBias:{},shadowNormalBias:{},shadowRadius:{},shadowMapSize:{}}},directionalShadowMatrix:{value:[]},spotLights:{value:[],properties:{color:{},position:{},direction:{},distance:{},coneCos:{},penumbraCos:{},decay:{}}},spotLightShadows:{value:[],properties:{shadowIntensity:1,shadowBias:{},shadowNormalBias:{},shadowRadius:{},shadowMapSize:{}}},spotLightMap:{value:[]},spotLightMatrix:{value:[]},pointLights:{value:[],properties:{color:{},position:{},decay:{},distance:{}}},pointLightShadows:{value:[],properties:{shadowIntensity:1,shadowBias:{},shadowNormalBias:{},shadowRadius:{},shadowMapSize:{},shadowCameraNear:{},shadowCameraFar:{}}},pointShadowMatrix:{value:[]},hemisphereLights:{value:[],properties:{direction:{},skyColor:{},groundColor:{}}},rectAreaLights:{value:[],properties:{color:{},position:{},width:{},height:{}}},ltc_1:{value:null},ltc_2:{value:null},probesSH:{value:null},probesMin:{value:new H},probesMax:{value:new H},probesResolution:{value:new H}},points:{diffuse:{value:new W(16777215)},opacity:{value:1},size:{value:1},scale:{value:1},map:{value:null},alphaMap:{value:null},alphaMapTransform:{value:new U},alphaTest:{value:0},uvTransform:{value:new U}},sprite:{diffuse:{value:new W(16777215)},opacity:{value:1},center:{value:new V(.5,.5)},rotation:{value:0},map:{value:null},mapTransform:{value:new U},alphaMap:{value:null},alphaMapTransform:{value:new U},alphaTest:{value:0}}},jf={basic:{uniforms:rd([q.common,q.specularmap,q.envmap,q.aomap,q.lightmap,q.fog]),vertexShader:K.meshbasic_vert,fragmentShader:K.meshbasic_frag},lambert:{uniforms:rd([q.common,q.specularmap,q.envmap,q.aomap,q.lightmap,q.emissivemap,q.bumpmap,q.normalmap,q.displacementmap,q.fog,q.lights,{emissive:{value:new W(0)},envMapIntensity:{value:1}}]),vertexShader:K.meshlambert_vert,fragmentShader:K.meshlambert_frag},phong:{uniforms:rd([q.common,q.specularmap,q.envmap,q.aomap,q.lightmap,q.emissivemap,q.bumpmap,q.normalmap,q.displacementmap,q.fog,q.lights,{emissive:{value:new W(0)},specular:{value:new W(1118481)},shininess:{value:30},envMapIntensity:{value:1}}]),vertexShader:K.meshphong_vert,fragmentShader:K.meshphong_frag},standard:{uniforms:rd([q.common,q.envmap,q.aomap,q.lightmap,q.emissivemap,q.bumpmap,q.normalmap,q.displacementmap,q.roughnessmap,q.metalnessmap,q.fog,q.lights,{emissive:{value:new W(0)},roughness:{value:1},metalness:{value:0},envMapIntensity:{value:1}}]),vertexShader:K.meshphysical_vert,fragmentShader:K.meshphysical_frag},toon:{uniforms:rd([q.common,q.aomap,q.lightmap,q.emissivemap,q.bumpmap,q.normalmap,q.displacementmap,q.gradientmap,q.fog,q.lights,{emissive:{value:new W(0)}}]),vertexShader:K.meshtoon_vert,fragmentShader:K.meshtoon_frag},matcap:{uniforms:rd([q.common,q.bumpmap,q.normalmap,q.displacementmap,q.fog,{matcap:{value:null}}]),vertexShader:K.meshmatcap_vert,fragmentShader:K.meshmatcap_frag},points:{uniforms:rd([q.points,q.fog]),vertexShader:K.points_vert,fragmentShader:K.points_frag},dashed:{uniforms:rd([q.common,q.fog,{scale:{value:1},dashSize:{value:1},totalSize:{value:2}}]),vertexShader:K.linedashed_vert,fragmentShader:K.linedashed_frag},depth:{uniforms:rd([q.common,q.displacementmap]),vertexShader:K.depth_vert,fragmentShader:K.depth_frag},normal:{uniforms:rd([q.common,q.bumpmap,q.normalmap,q.displacementmap,{opacity:{value:1}}]),vertexShader:K.meshnormal_vert,fragmentShader:K.meshnormal_frag},sprite:{uniforms:rd([q.sprite,q.fog]),vertexShader:K.sprite_vert,fragmentShader:K.sprite_frag},background:{uniforms:{uvTransform:{value:new U},t2D:{value:null},backgroundIntensity:{value:1}},vertexShader:K.background_vert,fragmentShader:K.background_frag},backgroundCube:{uniforms:{envMap:{value:null},backgroundBlurriness:{value:0},backgroundIntensity:{value:1},backgroundRotation:{value:new U}},vertexShader:K.backgroundCube_vert,fragmentShader:K.backgroundCube_frag},cube:{uniforms:{tCube:{value:null},tFlip:{value:-1},opacity:{value:1}},vertexShader:K.cube_vert,fragmentShader:K.cube_frag},equirect:{uniforms:{tEquirect:{value:null}},vertexShader:K.equirect_vert,fragmentShader:K.equirect_frag},distance:{uniforms:rd([q.common,q.displacementmap,{referencePosition:{value:new H},nearDistance:{value:1},farDistance:{value:1e3}}]),vertexShader:K.distance_vert,fragmentShader:K.distance_frag},shadow:{uniforms:rd([q.lights,q.fog,{color:{value:new W(0)},opacity:{value:1}}]),vertexShader:K.shadow_vert,fragmentShader:K.shadow_frag}};jf.physical={uniforms:rd([jf.standard.uniforms,{clearcoat:{value:0},clearcoatMap:{value:null},clearcoatMapTransform:{value:new U},clearcoatNormalMap:{value:null},clearcoatNormalMapTransform:{value:new U},clearcoatNormalScale:{value:new V(1,1)},clearcoatRoughness:{value:0},clearcoatRoughnessMap:{value:null},clearcoatRoughnessMapTransform:{value:new U},dispersion:{value:0},iridescence:{value:0},iridescenceMap:{value:null},iridescenceMapTransform:{value:new U},iridescenceIOR:{value:1.3},iridescenceThicknessMinimum:{value:100},iridescenceThicknessMaximum:{value:400},iridescenceThicknessMap:{value:null},iridescenceThicknessMapTransform:{value:new U},sheen:{value:0},sheenColor:{value:new W(0)},sheenColorMap:{value:null},sheenColorMapTransform:{value:new U},sheenRoughness:{value:1},sheenRoughnessMap:{value:null},sheenRoughnessMapTransform:{value:new U},transmission:{value:0},transmissionMap:{value:null},transmissionMapTransform:{value:new U},transmissionSamplerSize:{value:new V},transmissionSamplerMap:{value:null},thickness:{value:0},thicknessMap:{value:null},thicknessMapTransform:{value:new U},attenuationDistance:{value:0},attenuationColor:{value:new W(0)},specularColor:{value:new W(1,1,1)},specularColorMap:{value:null},specularColorMapTransform:{value:new U},specularIntensity:{value:1},specularIntensityMap:{value:null},specularIntensityMapTransform:{value:new U},anisotropyVector:{value:new V},anisotropyMap:{value:null},anisotropyMapTransform:{value:new U}}]),vertexShader:K.meshphysical_vert,fragmentShader:K.meshphysical_frag};var Mf={r:0,b:0,g:0},Nf=new fs,Pf=new U;Pf.set(-1,0,0,0,1,0,0,0,1);function Ff(e,t,n,r,i,a){let o=new W(0),s=i===!0?0:1,c,l,u=null,d=0,f=null;function p(e){let n=e.isScene===!0?e.background:null;if(n&&n.isTexture){let r=e.backgroundBlurriness>0;n=t.get(n,r)}return n}function m(t){let r=!1,i=p(t);i===null?g(o,s):i&&i.isColor&&(g(i,1),r=!0);let c=e.xr.getEnvironmentBlendMode();c===`additive`?n.buffers.color.setClear(0,0,0,1,a):c===`alpha-blend`&&n.buffers.color.setClear(0,0,0,0,a),(e.autoClear||r)&&(n.buffers.depth.setTest(!0),n.buffers.depth.setMask(!0),n.buffers.color.setMask(!0),e.clear(e.autoClearColor,e.autoClearDepth,e.autoClearStencil))}function h(t,n){let i=p(n);i&&(i.isCubeTexture||i.mapping===306)?(l===void 0&&(l=new kl(new mu(1,1,1),new ud({name:`BackgroundCubeMaterial`,uniforms:nd(jf.backgroundCube.uniforms),vertexShader:jf.backgroundCube.vertexShader,fragmentShader:jf.backgroundCube.fragmentShader,side:1,depthTest:!1,depthWrite:!1,fog:!1,allowOverride:!1})),l.geometry.deleteAttribute(`normal`),l.geometry.deleteAttribute(`uv`),l.onBeforeRender=function(e,t,n){this.matrixWorld.copyPosition(n.matrixWorld)},Object.defineProperty(l.material,"envMap",{get:function(){return this.uniforms.envMap.value}}),r.update(l)),l.material.uniforms.envMap.value=i,l.material.uniforms.backgroundBlurriness.value=n.backgroundBlurriness,l.material.uniforms.backgroundIntensity.value=n.backgroundIntensity,l.material.uniforms.backgroundRotation.value.setFromMatrix4(Nf.makeRotationFromEuler(n.backgroundRotation)).transpose(),i.isCubeTexture&&i.isRenderTargetTexture===!1&&l.material.uniforms.backgroundRotation.value.premultiply(Pf),l.material.toneMapped=Xo.getTransfer(i.colorSpace)!==eo,(u!==i||d!==i.version||f!==e.toneMapping)&&(l.material.needsUpdate=!0,u=i,d=i.version,f=e.toneMapping),l.layers.enableAll(),t.unshift(l,l.geometry,l.material,0,0,null)):i&&i.isTexture&&(c===void 0&&(c=new kl(new Yu(2,2),new ud({name:`BackgroundMaterial`,uniforms:nd(jf.background.uniforms),vertexShader:jf.background.vertexShader,fragmentShader:jf.background.fragmentShader,side:0,depthTest:!1,depthWrite:!1,fog:!1,allowOverride:!1})),c.geometry.deleteAttribute(`normal`),Object.defineProperty(c.material,"map",{get:function(){return this.uniforms.t2D.value}}),r.update(c)),c.material.uniforms.t2D.value=i,c.material.uniforms.backgroundIntensity.value=n.backgroundIntensity,c.material.toneMapped=Xo.getTransfer(i.colorSpace)!==eo,i.matrixAutoUpdate===!0&&i.updateMatrix(),c.material.uniforms.uvTransform.value.copy(i.matrix),(u!==i||d!==i.version||f!==e.toneMapping)&&(c.material.needsUpdate=!0,u=i,d=i.version,f=e.toneMapping),c.layers.enableAll(),t.unshift(c,c.geometry,c.material,0,0,null))}function g(t,r){t.getRGB(Mf,od(e)),n.buffers.color.setClear(Mf.r,Mf.g,Mf.b,r,a)}function _(){l!==void 0&&(l.geometry.dispose(),l.material.dispose(),l=void 0),c!==void 0&&(c.geometry.dispose(),c.material.dispose(),c=void 0)}return{getClearColor:function(){return o},setClearColor:function(e,t=1){o.set(e),s=t,g(o,s)},getClearAlpha:function(){return s},setClearAlpha:function(e){s=e,g(o,s)},render:m,addToRenderList:h,dispose:_}}function If(e,t){let n=e.getParameter(e.MAX_VERTEX_ATTRIBS),r={},i=f(null),a=i,o=!1;function s(n,r,i,s,c){let u=!1,f=d(n,s,i,r);a!==f&&(a=f,l(a.object)),u=p(n,s,i,c),u&&m(n,s,i,c),c!==null&&t.update(c,e.ELEMENT_ARRAY_BUFFER),(u||o)&&(o=!1,b(n,r,i,s),c!==null&&e.bindBuffer(e.ELEMENT_ARRAY_BUFFER,t.get(c).buffer))}function c(){return e.createVertexArray()}function l(t){return e.bindVertexArray(t)}function u(t){return e.deleteVertexArray(t)}function d(e,t,n,i){let a=i.wireframe===!0,o=r[t.id];o===void 0&&(o={},r[t.id]=o);let s=e.isInstancedMesh===!0?e.id:0,l=o[s];l===void 0&&(l={},o[s]=l);let u=l[n.id];u===void 0&&(u={},l[n.id]=u);let d=u[a];return d===void 0&&(d=f(c()),u[a]=d),d}function f(e){let t=[],r=[],i=[];for(let e=0;e<n;e++)t[e]=0,r[e]=0,i[e]=0;return{geometry:null,program:null,wireframe:!1,newAttributes:t,enabledAttributes:r,attributeDivisors:i,object:e,attributes:{},index:null}}function p(e,t,n,r){let i=a.attributes,o=t.attributes,s=0,c=n.getAttributes();for(let t in c)if(c[t].location>=0){let n=i[t],r=o[t];if(r===void 0&&(t===`instanceMatrix`&&e.instanceMatrix&&(r=e.instanceMatrix),t===`instanceColor`&&e.instanceColor&&(r=e.instanceColor)),n===void 0||n.attribute!==r||r&&n.data!==r.data)return!0;s++}return a.attributesNum!==s||a.index!==r}function m(e,t,n,r){let i={},o=t.attributes,s=0,c=n.getAttributes();for(let t in c)if(c[t].location>=0){let n=o[t];n===void 0&&(t===`instanceMatrix`&&e.instanceMatrix&&(n=e.instanceMatrix),t===`instanceColor`&&e.instanceColor&&(n=e.instanceColor));let r={};r.attribute=n,n&&n.data&&(r.data=n.data),i[t]=r,s++}a.attributes=i,a.attributesNum=s,a.index=r}function h(){let e=a.newAttributes;for(let t=0,n=e.length;t<n;t++)e[t]=0}function g(e){_(e,0)}function _(t,n){let r=a.newAttributes,i=a.enabledAttributes,o=a.attributeDivisors;r[t]=1,i[t]===0&&(e.enableVertexAttribArray(t),i[t]=1),o[t]!==n&&(e.vertexAttribDivisor(t,n),o[t]=n)}function v(){let t=a.newAttributes,n=a.enabledAttributes;for(let r=0,i=n.length;r<i;r++)n[r]!==t[r]&&(e.disableVertexAttribArray(r),n[r]=0)}function y(t,n,r,i,a,o,s){s===!0?e.vertexAttribIPointer(t,n,r,a,o):e.vertexAttribPointer(t,n,r,i,a,o)}function b(n,r,i,a){h();let o=a.attributes,s=i.getAttributes(),c=r.defaultAttributeValues;for(let r in s){let i=s[r];if(i.location>=0){let s=o[r];if(s===void 0&&(r===`instanceMatrix`&&n.instanceMatrix&&(s=n.instanceMatrix),r===`instanceColor`&&n.instanceColor&&(s=n.instanceColor)),s!==void 0){let r=s.normalized,o=s.itemSize,c=t.get(s);if(c===void 0)continue;let l=c.buffer,u=c.type,d=c.bytesPerElement,f=u===e.INT||u===e.UNSIGNED_INT||s.gpuType===1013;if(s.isInterleavedBufferAttribute){let t=s.data,c=t.stride,p=s.offset;if(t.isInstancedInterleavedBuffer){for(let e=0;e<i.locationSize;e++)_(i.location+e,t.meshPerAttribute);n.isInstancedMesh!==!0&&a._maxInstanceCount===void 0&&(a._maxInstanceCount=t.meshPerAttribute*t.count)}else for(let e=0;e<i.locationSize;e++)g(i.location+e);e.bindBuffer(e.ARRAY_BUFFER,l);for(let e=0;e<i.locationSize;e++)y(i.location+e,o/i.locationSize,u,r,c*d,(p+o/i.locationSize*e)*d,f)}else{if(s.isInstancedBufferAttribute){for(let e=0;e<i.locationSize;e++)_(i.location+e,s.meshPerAttribute);n.isInstancedMesh!==!0&&a._maxInstanceCount===void 0&&(a._maxInstanceCount=s.meshPerAttribute*s.count)}else for(let e=0;e<i.locationSize;e++)g(i.location+e);e.bindBuffer(e.ARRAY_BUFFER,l);for(let e=0;e<i.locationSize;e++)y(i.location+e,o/i.locationSize,u,r,o*d,o/i.locationSize*e*d,f)}}else if(c!==void 0){let t=c[r];if(t!==void 0)switch(t.length){case 2:e.vertexAttrib2fv(i.location,t);break;case 3:e.vertexAttrib3fv(i.location,t);break;case 4:e.vertexAttrib4fv(i.location,t);break;default:e.vertexAttrib1fv(i.location,t)}}}}v()}function x(){T();for(let e in r){let t=r[e];for(let e in t){let n=t[e];for(let e in n){let t=n[e];for(let e in t)u(t[e].object),delete t[e];delete n[e]}}delete r[e]}}function S(e){if(r[e.id]===void 0)return;let t=r[e.id];for(let e in t){let n=t[e];for(let e in n){let t=n[e];for(let e in t)u(t[e].object),delete t[e];delete n[e]}}delete r[e.id]}function C(e){for(let t in r){let n=r[t];for(let t in n){let r=n[t];if(r[e.id]===void 0)continue;let i=r[e.id];for(let e in i)u(i[e].object),delete i[e];delete r[e.id]}}}function w(e){for(let t in r){let n=r[t],i=e.isInstancedMesh===!0?e.id:0,a=n[i];if(a!==void 0){for(let e in a){let t=a[e];for(let e in t)u(t[e].object),delete t[e];delete a[e]}delete n[i],Object.keys(n).length===0&&delete r[t]}}}function T(){E(),o=!0,a!==i&&(a=i,l(a.object))}function E(){i.geometry=null,i.program=null,i.wireframe=!1}return{setup:s,reset:T,resetDefaultState:E,dispose:x,releaseStatesOfGeometry:S,releaseStatesOfObject:w,releaseStatesOfProgram:C,initAttributes:h,enableAttribute:g,disableUnusedAttributes:v}}function Lf(e,t,n){let r;function i(e){r=e}function a(t,i){e.drawArrays(r,t,i),n.update(i,r,1)}function o(t,i,a){a!==0&&(e.drawArraysInstanced(r,t,i,a),n.update(i,r,a))}function s(e,i,a){if(a===0)return;t.get(`WEBGL_multi_draw`).multiDrawArraysWEBGL(r,e,0,i,0,a);let o=0;for(let e=0;e<a;e++)o+=i[e];n.update(o,r,1)}this.setMode=i,this.render=a,this.renderInstances=o,this.renderMultiDraw=s}function Rf(e,t,n,r){let i;function a(){if(i!==void 0)return i;if(t.has(`EXT_texture_filter_anisotropic`)===!0){let n=t.get(`EXT_texture_filter_anisotropic`);i=e.getParameter(n.MAX_TEXTURE_MAX_ANISOTROPY_EXT)}else i=0;return i}function o(t){return!(t!==1023&&r.convert(t)!==e.getParameter(e.IMPLEMENTATION_COLOR_READ_FORMAT))}function s(n){let i=n===1016&&(t.has(`EXT_color_buffer_half_float`)||t.has(`EXT_color_buffer_float`));return!(n!==1009&&r.convert(n)!==e.getParameter(e.IMPLEMENTATION_COLOR_READ_TYPE)&&n!==1015&&!i)}function c(t){if(t===`highp`){if(e.getShaderPrecisionFormat(e.VERTEX_SHADER,e.HIGH_FLOAT).precision>0&&e.getShaderPrecisionFormat(e.FRAGMENT_SHADER,e.HIGH_FLOAT).precision>0)return`highp`;t=`mediump`}return t===`mediump`&&e.getShaderPrecisionFormat(e.VERTEX_SHADER,e.MEDIUM_FLOAT).precision>0&&e.getShaderPrecisionFormat(e.FRAGMENT_SHADER,e.MEDIUM_FLOAT).precision>0?`mediump`:`lowp`}let l=n.precision===void 0?`highp`:n.precision,u=c(l);u!==l&&(R(`WebGLRenderer:`,l,`not supported, using`,u,`instead.`),l=u);let d=n.logarithmicDepthBuffer===!0,f=n.reversedDepthBuffer===!0&&t.has(`EXT_clip_control`);n.reversedDepthBuffer===!0&&f===!1&&R(`WebGLRenderer: Unable to use reversed depth buffer due to missing EXT_clip_control extension. Fallback to default depth buffer.`);let p=e.getParameter(e.MAX_TEXTURE_IMAGE_UNITS),m=e.getParameter(e.MAX_VERTEX_TEXTURE_IMAGE_UNITS),h=e.getParameter(e.MAX_TEXTURE_SIZE),g=e.getParameter(e.MAX_CUBE_MAP_TEXTURE_SIZE),_=e.getParameter(e.MAX_VERTEX_ATTRIBS),v=e.getParameter(e.MAX_VERTEX_UNIFORM_VECTORS),y=e.getParameter(e.MAX_VARYING_VECTORS),b=e.getParameter(e.MAX_FRAGMENT_UNIFORM_VECTORS),x=e.getParameter(e.MAX_SAMPLES),S=e.getParameter(e.SAMPLES);return{isWebGL2:!0,getMaxAnisotropy:a,getMaxPrecision:c,textureFormatReadable:o,textureTypeReadable:s,precision:l,logarithmicDepthBuffer:d,reversedDepthBuffer:f,maxTextures:p,maxVertexTextures:m,maxTextureSize:h,maxCubemapSize:g,maxAttributes:_,maxVertexUniforms:v,maxVaryings:y,maxFragmentUniforms:b,maxSamples:x,samples:S}}function zf(e){let t=this,n=null,r=0,i=!1,a=!1,o=new Gl,s=new U,c={value:null,needsUpdate:!1};this.uniform=c,this.numPlanes=0,this.numIntersection=0,this.init=function(e,t){let n=e.length!==0||t||r!==0||i;return i=t,r=e.length,n},this.beginShadows=function(){a=!0,u(null)},this.endShadows=function(){a=!1},this.setGlobalState=function(e,t){n=u(e,t,0)},this.setState=function(t,o,s){let d=t.clippingPlanes,f=t.clipIntersection,p=t.clipShadows,m=e.get(t);if(!i||d===null||d.length===0||a&&!p)a?u(null):l();else{let e=a?0:r,t=e*4,i=m.clippingState||null;c.value=i,i=u(d,o,t,s);for(let e=0;e!==t;++e)i[e]=n[e];m.clippingState=i,this.numIntersection=f?this.numPlanes:0,this.numPlanes+=e}};function l(){c.value!==n&&(c.value=n,c.needsUpdate=r>0),t.numPlanes=r,t.numIntersection=0}function u(e,n,r,i){let a=e===null?0:e.length,l=null;if(a!==0){if(l=c.value,i!==!0||l===null){let t=r+a*4,i=n.matrixWorldInverse;s.getNormalMatrix(i),(l===null||l.length<t)&&(l=new Float32Array(t));for(let t=0,n=r;t!==a;++t,n+=4)o.copy(e[t]).applyMatrix4(i,s),o.normal.toArray(l,n),l[n+3]=o.constant}c.value=l,c.needsUpdate=!0}return t.numPlanes=a,t.numIntersection=0,l}}var Bf=4,Vf=[.125,.215,.35,.446,.526,.582],Hf=20,Uf=256,Wf=new Kd,Gf=new W,Kf=null,qf=0,Jf=0,Yf=!1,Xf=new H,Zf=class{constructor(e){this._renderer=e,this._pingPongRenderTarget=null,this._lodMax=0,this._cubeSize=0,this._sizeLods=[],this._sigmas=[],this._lodMeshes=[],this._backgroundBox=null,this._cubemapMaterial=null,this._equirectMaterial=null,this._blurMaterial=null,this._ggxMaterial=null}fromScene(e,t=0,n=.1,r=100,i={}){let{size:a=256,position:o=Xf}=i;Kf=this._renderer.getRenderTarget(),qf=this._renderer.getActiveCubeFace(),Jf=this._renderer.getActiveMipmapLevel(),Yf=this._renderer.xr.enabled,this._renderer.xr.enabled=!1,this._setSize(a);let s=this._allocateTargets();return s.depthBuffer=!0,this._sceneToCubeUV(e,n,r,s,o),t>0&&this._blur(s,0,0,t),this._applyPMREM(s),this._cleanup(s),s}fromEquirectangular(e,t=null){return this._fromTexture(e,t)}fromCubemap(e,t=null){return this._fromTexture(e,t)}compileCubemapShader(){this._cubemapMaterial===null&&(this._cubemapMaterial=ip(),this._compileMaterial(this._cubemapMaterial))}compileEquirectangularShader(){this._equirectMaterial===null&&(this._equirectMaterial=rp(),this._compileMaterial(this._equirectMaterial))}dispose(){this._dispose(),this._cubemapMaterial!==null&&this._cubemapMaterial.dispose(),this._equirectMaterial!==null&&this._equirectMaterial.dispose(),this._backgroundBox!==null&&(this._backgroundBox.geometry.dispose(),this._backgroundBox.material.dispose())}_setSize(e){this._lodMax=Math.floor(Math.log2(e)),this._cubeSize=2**this._lodMax}_dispose(){this._blurMaterial!==null&&this._blurMaterial.dispose(),this._ggxMaterial!==null&&this._ggxMaterial.dispose(),this._pingPongRenderTarget!==null&&this._pingPongRenderTarget.dispose();for(let e=0;e<this._lodMeshes.length;e++)this._lodMeshes[e].geometry.dispose()}_cleanup(e){this._renderer.setRenderTarget(Kf,qf,Jf),this._renderer.xr.enabled=Yf,e.scissorTest=!1,ep(e,0,0,e.width,e.height)}_fromTexture(e,t){e.mapping===301||e.mapping===302?this._setSize(e.image.length===0?16:e.image[0].width||e.image[0].image.width):this._setSize(e.image.width/4),Kf=this._renderer.getRenderTarget(),qf=this._renderer.getActiveCubeFace(),Jf=this._renderer.getActiveMipmapLevel(),Yf=this._renderer.xr.enabled,this._renderer.xr.enabled=!1;let n=t||this._allocateTargets();return this._textureToCubeUV(e,n),this._applyPMREM(n),this._cleanup(n),n}_allocateTargets(){let e=3*Math.max(this._cubeSize,112),t=4*this._cubeSize,n={magFilter:Pi,minFilter:Pi,generateMipmaps:!1,type:Wi,format:Qi,colorSpace:Qa,depthBuffer:!1},r=$f(e,t,n);if(this._pingPongRenderTarget===null||this._pingPongRenderTarget.width!==e||this._pingPongRenderTarget.height!==t){this._pingPongRenderTarget!==null&&this._dispose(),this._pingPongRenderTarget=$f(e,t,n);let{_lodMax:r}=this;({lodMeshes:this._lodMeshes,sizeLods:this._sizeLods,sigmas:this._sigmas}=Qf(r)),this._blurMaterial=np(r,e,t),this._ggxMaterial=tp(r,e,t)}return r}_compileMaterial(e){let t=new kl(new Vc,e);this._renderer.compile(t,Wf)}_sceneToCubeUV(e,t,n,r,i){let a=new Gd(90,1,t,n),o=[1,-1,1,1,1,1],s=[1,1,1,-1,-1,-1],c=this._renderer,l=c.autoClear,u=c.toneMapping;c.getClearColor(Gf),c.toneMapping=0,c.autoClear=!1,c.state.buffers.depth.getReversed()&&(c.setRenderTarget(r),c.clearDepth(),c.setRenderTarget(null)),this._backgroundBox===null&&(this._backgroundBox=new kl(new mu,new _l({name:`PMREM.Background`,side:1,depthWrite:!1,depthTest:!1})));let d=this._backgroundBox,f=d.material,p=!1,m=e.background;m?m.isColor&&(f.color.copy(m),e.background=null,p=!0):(f.color.copy(Gf),p=!0);for(let t=0;t<6;t++){let n=t%3;n===0?(a.up.set(0,o[t],0),a.position.set(i.x,i.y,i.z),a.lookAt(i.x+s[t],i.y,i.z)):n===1?(a.up.set(0,0,o[t]),a.position.set(i.x,i.y,i.z),a.lookAt(i.x,i.y+s[t],i.z)):(a.up.set(0,o[t],0),a.position.set(i.x,i.y,i.z),a.lookAt(i.x,i.y,i.z+s[t]));let l=this._cubeSize;ep(r,n*l,t>2?l:0,l,l),c.setRenderTarget(r),p&&c.render(d,a),c.render(e,a)}c.toneMapping=u,c.autoClear=l,e.background=m}_textureToCubeUV(e,t){let n=this._renderer,r=e.mapping===301||e.mapping===302;r?(this._cubemapMaterial===null&&(this._cubemapMaterial=ip()),this._cubemapMaterial.uniforms.flipEnvMap.value=e.isRenderTargetTexture===!1?-1:1):this._equirectMaterial===null&&(this._equirectMaterial=rp());let i=r?this._cubemapMaterial:this._equirectMaterial,a=this._lodMeshes[0];a.material=i;let o=i.uniforms;o.envMap.value=e;let s=this._cubeSize;ep(t,0,0,3*s,2*s),n.setRenderTarget(t),n.render(a,Wf)}_applyPMREM(e){let t=this._renderer,n=t.autoClear;t.autoClear=!1;let r=this._lodMeshes.length;for(let t=1;t<r;t++)this._applyGGXFilter(e,t-1,t);t.autoClear=n}_applyGGXFilter(e,t,n){let r=this._renderer,i=this._pingPongRenderTarget,a=this._ggxMaterial,o=this._lodMeshes[n];o.material=a;let s=a.uniforms,c=n/(this._lodMeshes.length-1),l=t/(this._lodMeshes.length-1),u=Math.sqrt(c*c-l*l)*(0+c*1.25),{_lodMax:d}=this,f=this._sizeLods[n],p=3*f*(n>d-Bf?n-d+Bf:0),m=4*(this._cubeSize-f);s.envMap.value=e.texture,s.roughness.value=u,s.mipInt.value=d-t,ep(i,p,m,3*f,2*f),r.setRenderTarget(i),r.render(o,Wf),s.envMap.value=i.texture,s.roughness.value=0,s.mipInt.value=d-n,ep(e,p,m,3*f,2*f),r.setRenderTarget(e),r.render(o,Wf)}_blur(e,t,n,r,i){let a=this._pingPongRenderTarget;this._halfBlur(e,a,t,n,r,`latitudinal`,i),this._halfBlur(a,e,n,n,r,`longitudinal`,i)}_halfBlur(e,t,n,r,i,a,o){let s=this._renderer,c=this._blurMaterial;a!==`latitudinal`&&a!==`longitudinal`&&z(`blur direction must be either latitudinal or longitudinal!`);let l=this._lodMeshes[r];l.material=c;let u=c.uniforms,d=this._sizeLods[n]-1,f=isFinite(i)?Math.PI/(2*d):2*Math.PI/(2*Hf-1),p=i/f,m=isFinite(i)?1+Math.floor(3*p):Hf;m>Hf&&R(`sigmaRadians, ${i}, is too large and will clip, as it requested ${m} samples when the maximum is set to ${Hf}`);let h=[],g=0;for(let e=0;e<Hf;++e){let t=e/p,n=Math.exp(-t*t/2);h.push(n),e===0?g+=n:e<m&&(g+=2*n)}for(let e=0;e<h.length;e++)h[e]=h[e]/g;u.envMap.value=e.texture,u.samples.value=m,u.weights.value=h,u.latitudinal.value=a===`latitudinal`,o&&(u.poleAxis.value=o);let{_lodMax:_}=this;u.dTheta.value=f,u.mipInt.value=_-n;let v=this._sizeLods[r];ep(t,3*v*(r>_-Bf?r-_+Bf:0),4*(this._cubeSize-v),3*v,2*v),s.setRenderTarget(t),s.render(l,Wf)}};function Qf(e){let t=[],n=[],r=[],i=e,a=e-Bf+1+Vf.length;for(let o=0;o<a;o++){let a=2**i;t.push(a);let s=1/a;o>e-Bf?s=Vf[o-e+Bf-1]:o===0&&(s=0),n.push(s);let c=1/(a-2),l=-c,u=1+c,d=[l,l,u,l,u,u,l,l,u,u,l,u],f=new Float32Array(108),p=new Float32Array(72),m=new Float32Array(36);for(let e=0;e<6;e++){let t=e%3*2/3-1,n=e>2?0:-1,r=[t,n,0,t+2/3,n,0,t+2/3,n+1,0,t,n,0,t+2/3,n+1,0,t,n+1,0];f.set(r,18*e),p.set(d,12*e);let i=[e,e,e,e,e,e];m.set(i,6*e)}let h=new Vc;h.setAttribute(`position`,new Dc(f,3)),h.setAttribute(`uv`,new Dc(p,2)),h.setAttribute(`faceIndex`,new Dc(m,1)),r.push(new kl(h,null)),i>Bf&&i--}return{lodMeshes:r,sizeLods:t,sigmas:n}}function $f(e,t,n){let r=new ls(e,t,n);return r.texture.mapping=306,r.texture.name=`PMREM.cubeUv`,r.scissorTest=!0,r}function ep(e,t,n,r,i){e.viewport.set(t,n,r,i),e.scissor.set(t,n,r,i)}function tp(e,t,n){return new ud({name:`PMREMGGXConvolution`,defines:{GGX_SAMPLES:Uf,CUBEUV_TEXEL_WIDTH:1/t,CUBEUV_TEXEL_HEIGHT:1/n,CUBEUV_MAX_MIP:`${e}.0`},uniforms:{envMap:{value:null},roughness:{value:0},mipInt:{value:0}},vertexShader:ap(),fragmentShader:`

			precision highp float;
			precision highp int;

			varying vec3 vOutputDirection;

			uniform sampler2D envMap;
			uniform float roughness;
			uniform float mipInt;

			#define ENVMAP_TYPE_CUBE_UV
			#include <cube_uv_reflection_fragment>

			#define PI 3.14159265359

			// Van der Corput radical inverse
			float radicalInverse_VdC(uint bits) {
				bits = (bits << 16u) | (bits >> 16u);
				bits = ((bits & 0x55555555u) << 1u) | ((bits & 0xAAAAAAAAu) >> 1u);
				bits = ((bits & 0x33333333u) << 2u) | ((bits & 0xCCCCCCCCu) >> 2u);
				bits = ((bits & 0x0F0F0F0Fu) << 4u) | ((bits & 0xF0F0F0F0u) >> 4u);
				bits = ((bits & 0x00FF00FFu) << 8u) | ((bits & 0xFF00FF00u) >> 8u);
				return float(bits) * 2.3283064365386963e-10; // / 0x100000000
			}

			// Hammersley sequence
			vec2 hammersley(uint i, uint N) {
				return vec2(float(i) / float(N), radicalInverse_VdC(i));
			}

			// GGX VNDF importance sampling (Eric Heitz 2018)
			// "Sampling the GGX Distribution of Visible Normals"
			// https://jcgt.org/published/0007/04/01/
			vec3 importanceSampleGGX_VNDF(vec2 Xi, vec3 V, float roughness) {
				float alpha = roughness * roughness;

				// Section 4.1: Orthonormal basis
				vec3 T1 = vec3(1.0, 0.0, 0.0);
				vec3 T2 = cross(V, T1);

				// Section 4.2: Parameterization of projected area
				float r = sqrt(Xi.x);
				float phi = 2.0 * PI * Xi.y;
				float t1 = r * cos(phi);
				float t2 = r * sin(phi);
				float s = 0.5 * (1.0 + V.z);
				t2 = (1.0 - s) * sqrt(1.0 - t1 * t1) + s * t2;

				// Section 4.3: Reprojection onto hemisphere
				vec3 Nh = t1 * T1 + t2 * T2 + sqrt(max(0.0, 1.0 - t1 * t1 - t2 * t2)) * V;

				// Section 3.4: Transform back to ellipsoid configuration
				return normalize(vec3(alpha * Nh.x, alpha * Nh.y, max(0.0, Nh.z)));
			}

			void main() {
				vec3 N = normalize(vOutputDirection);
				vec3 V = N; // Assume view direction equals normal for pre-filtering

				vec3 prefilteredColor = vec3(0.0);
				float totalWeight = 0.0;

				// For very low roughness, just sample the environment directly
				if (roughness < 0.001) {
					gl_FragColor = vec4(bilinearCubeUV(envMap, N, mipInt), 1.0);
					return;
				}

				// Tangent space basis for VNDF sampling
				vec3 up = abs(N.z) < 0.999 ? vec3(0.0, 0.0, 1.0) : vec3(1.0, 0.0, 0.0);
				vec3 tangent = normalize(cross(up, N));
				vec3 bitangent = cross(N, tangent);

				for(uint i = 0u; i < uint(GGX_SAMPLES); i++) {
					vec2 Xi = hammersley(i, uint(GGX_SAMPLES));

					// For PMREM, V = N, so in tangent space V is always (0, 0, 1)
					vec3 H_tangent = importanceSampleGGX_VNDF(Xi, vec3(0.0, 0.0, 1.0), roughness);

					// Transform H back to world space
					vec3 H = normalize(tangent * H_tangent.x + bitangent * H_tangent.y + N * H_tangent.z);
					vec3 L = normalize(2.0 * dot(V, H) * H - V);

					float NdotL = max(dot(N, L), 0.0);

					if(NdotL > 0.0) {
						// Sample environment at fixed mip level
						// VNDF importance sampling handles the distribution filtering
						vec3 sampleColor = bilinearCubeUV(envMap, L, mipInt);

						// Weight by NdotL for the split-sum approximation
						// VNDF PDF naturally accounts for the visible microfacet distribution
						prefilteredColor += sampleColor * NdotL;
						totalWeight += NdotL;
					}
				}

				if (totalWeight > 0.0) {
					prefilteredColor = prefilteredColor / totalWeight;
				}

				gl_FragColor = vec4(prefilteredColor, 1.0);
			}
		`,blending:0,depthTest:!1,depthWrite:!1})}function np(e,t,n){let r=new Float32Array(Hf),i=new H(0,1,0);return new ud({name:`SphericalGaussianBlur`,defines:{n:Hf,CUBEUV_TEXEL_WIDTH:1/t,CUBEUV_TEXEL_HEIGHT:1/n,CUBEUV_MAX_MIP:`${e}.0`},uniforms:{envMap:{value:null},samples:{value:1},weights:{value:r},latitudinal:{value:!1},dTheta:{value:0},mipInt:{value:0},poleAxis:{value:i}},vertexShader:ap(),fragmentShader:`

			precision mediump float;
			precision mediump int;

			varying vec3 vOutputDirection;

			uniform sampler2D envMap;
			uniform int samples;
			uniform float weights[ n ];
			uniform bool latitudinal;
			uniform float dTheta;
			uniform float mipInt;
			uniform vec3 poleAxis;

			#define ENVMAP_TYPE_CUBE_UV
			#include <cube_uv_reflection_fragment>

			vec3 getSample( float theta, vec3 axis ) {

				float cosTheta = cos( theta );
				// Rodrigues' axis-angle rotation
				vec3 sampleDirection = vOutputDirection * cosTheta
					+ cross( axis, vOutputDirection ) * sin( theta )
					+ axis * dot( axis, vOutputDirection ) * ( 1.0 - cosTheta );

				return bilinearCubeUV( envMap, sampleDirection, mipInt );

			}

			void main() {

				vec3 axis = latitudinal ? poleAxis : cross( poleAxis, vOutputDirection );

				if ( all( equal( axis, vec3( 0.0 ) ) ) ) {

					axis = vec3( vOutputDirection.z, 0.0, - vOutputDirection.x );

				}

				axis = normalize( axis );

				gl_FragColor = vec4( 0.0, 0.0, 0.0, 1.0 );
				gl_FragColor.rgb += weights[ 0 ] * getSample( 0.0, axis );

				for ( int i = 1; i < n; i++ ) {

					if ( i >= samples ) {

						break;

					}

					float theta = dTheta * float( i );
					gl_FragColor.rgb += weights[ i ] * getSample( -1.0 * theta, axis );
					gl_FragColor.rgb += weights[ i ] * getSample( theta, axis );

				}

			}
		`,blending:0,depthTest:!1,depthWrite:!1})}function rp(){return new ud({name:`EquirectangularToCubeUV`,uniforms:{envMap:{value:null}},vertexShader:ap(),fragmentShader:`

			precision mediump float;
			precision mediump int;

			varying vec3 vOutputDirection;

			uniform sampler2D envMap;

			#include <common>

			void main() {

				vec3 outputDirection = normalize( vOutputDirection );
				vec2 uv = equirectUv( outputDirection );

				gl_FragColor = vec4( texture2D ( envMap, uv ).rgb, 1.0 );

			}
		`,blending:0,depthTest:!1,depthWrite:!1})}function ip(){return new ud({name:`CubemapToCubeUV`,uniforms:{envMap:{value:null},flipEnvMap:{value:-1}},vertexShader:ap(),fragmentShader:`

			precision mediump float;
			precision mediump int;

			uniform float flipEnvMap;

			varying vec3 vOutputDirection;

			uniform samplerCube envMap;

			void main() {

				gl_FragColor = textureCube( envMap, vec3( flipEnvMap * vOutputDirection.x, vOutputDirection.yz ) );

			}
		`,blending:0,depthTest:!1,depthWrite:!1})}function ap(){return`

		precision mediump float;
		precision mediump int;

		attribute float faceIndex;

		varying vec3 vOutputDirection;

		// RH coordinate system; PMREM face-indexing convention
		vec3 getDirection( vec2 uv, float face ) {

			uv = 2.0 * uv - 1.0;

			vec3 direction = vec3( uv, 1.0 );

			if ( face == 0.0 ) {

				direction = direction.zyx; // ( 1, v, u ) pos x

			} else if ( face == 1.0 ) {

				direction = direction.xzy;
				direction.xz *= -1.0; // ( -u, 1, -v ) pos y

			} else if ( face == 2.0 ) {

				direction.x *= -1.0; // ( -u, v, 1 ) pos z

			} else if ( face == 3.0 ) {

				direction = direction.zyx;
				direction.xz *= -1.0; // ( -1, v, -u ) neg x

			} else if ( face == 4.0 ) {

				direction = direction.xzy;
				direction.xy *= -1.0; // ( -u, -1, v ) neg y

			} else if ( face == 5.0 ) {

				direction.z *= -1.0; // ( u, v, -1 ) neg z

			}

			return direction;

		}

		void main() {

			vOutputDirection = getDirection( uv, faceIndex );
			gl_Position = vec4( position, 1.0 );

		}
	`}var op=class extends ls{constructor(e=1,t={}){super(e,e,t),this.isWebGLCubeRenderTarget=!0;let n={width:e,height:e,depth:1},r=[n,n,n,n,n,n];this.texture=new lu(r),this._setTextureOptions(t),this.texture.isRenderTargetTexture=!0}fromEquirectangularTexture(e,t){this.texture.type=t.type,this.texture.colorSpace=t.colorSpace,this.texture.generateMipmaps=t.generateMipmaps,this.texture.minFilter=t.minFilter,this.texture.magFilter=t.magFilter;let n={uniforms:{tEquirect:{value:null}},vertexShader:`

				varying vec3 vWorldDirection;

				vec3 transformDirection( in vec3 dir, in mat4 matrix ) {

					return normalize( ( matrix * vec4( dir, 0.0 ) ).xyz );

				}

				void main() {

					vWorldDirection = transformDirection( position, modelMatrix );

					#include <begin_vertex>
					#include <project_vertex>

				}
			`,fragmentShader:`

				uniform sampler2D tEquirect;

				varying vec3 vWorldDirection;

				#include <common>

				void main() {

					vec3 direction = normalize( vWorldDirection );

					vec2 sampleUV = equirectUv( direction );

					gl_FragColor = texture2D( tEquirect, sampleUV );

				}
			`},r=new mu(5,5,5),i=new ud({name:`CubemapFromEquirect`,uniforms:nd(n.uniforms),vertexShader:n.vertexShader,fragmentShader:n.fragmentShader,side:1,blending:0});i.uniforms.tEquirect.value=t;let a=new kl(r,i),o=t.minFilter;return t.minFilter===1008&&(t.minFilter=Pi),new Zd(1,10,this).update(e,a),t.minFilter=o,a.geometry.dispose(),a.material.dispose(),this}clear(e,t=!0,n=!0,r=!0){let i=e.getRenderTarget();for(let i=0;i<6;i++)e.setRenderTarget(this,i),e.clear(t,n,r);e.setRenderTarget(i)}};function sp(e){let t=new WeakMap,n=new WeakMap,r=null;function i(e,t=!1){return e==null?null:t?o(e):a(e)}function a(n){if(n&&n.isTexture){let r=n.mapping;if(r===303||r===304)if(t.has(n)){let e=t.get(n).texture;return s(e,n.mapping)}else{let r=n.image;if(r&&r.height>0){let i=new op(r.height);return i.fromEquirectangularTexture(e,n),t.set(n,i),n.addEventListener(`dispose`,l),s(i.texture,n.mapping)}else return null}}return n}function o(t){if(t&&t.isTexture){let i=t.mapping,a=i===303||i===304,o=i===301||i===302;if(a||o){let i=n.get(t),s=i===void 0?0:i.texture.pmremVersion;if(t.isRenderTargetTexture&&t.pmremVersion!==s)return r===null&&(r=new Zf(e)),i=a?r.fromEquirectangular(t,i):r.fromCubemap(t,i),i.texture.pmremVersion=t.pmremVersion,n.set(t,i),i.texture;if(i!==void 0)return i.texture;{let s=t.image;return a&&s&&s.height>0||o&&s&&c(s)?(r===null&&(r=new Zf(e)),i=a?r.fromEquirectangular(t):r.fromCubemap(t),i.texture.pmremVersion=t.pmremVersion,n.set(t,i),t.addEventListener(`dispose`,u),i.texture):null}}}return t}function s(e,t){return t===303?e.mapping=301:t===304&&(e.mapping=302),e}function c(e){let t=0;for(let n=0;n<6;n++)e[n]!==void 0&&t++;return t===6}function l(e){let n=e.target;n.removeEventListener(`dispose`,l);let r=t.get(n);r!==void 0&&(t.delete(n),r.dispose())}function u(e){let t=e.target;t.removeEventListener(`dispose`,u);let r=n.get(t);r!==void 0&&(n.delete(t),r.dispose())}function d(){t=new WeakMap,n=new WeakMap,r!==null&&(r.dispose(),r=null)}return{get:i,dispose:d}}function cp(e){let t={};function n(n){if(t[n]!==void 0)return t[n];let r=e.getExtension(n);return t[n]=r,r}return{has:function(e){return n(e)!==null},init:function(){n(`EXT_color_buffer_float`),n(`WEBGL_clip_cull_distance`),n(`OES_texture_float_linear`),n(`EXT_color_buffer_half_float`),n(`WEBGL_multisampled_render_to_texture`),n(`WEBGL_render_shared_exponent`)},get:function(e){let t=n(e);return t===null&&po(`WebGLRenderer: `+e+` extension not supported.`),t}}}function lp(e,t,n,r){let i={},a=new WeakMap;function o(e){let s=e.target;s.index!==null&&t.remove(s.index);for(let e in s.attributes)t.remove(s.attributes[e]);s.removeEventListener(`dispose`,o),delete i[s.id];let c=a.get(s);c&&(t.remove(c),a.delete(s)),r.releaseStatesOfGeometry(s),s.isInstancedBufferGeometry===!0&&delete s._maxInstanceCount,n.memory.geometries--}function s(e,t){return i[t.id]===!0?t:(t.addEventListener(`dispose`,o),i[t.id]=!0,n.memory.geometries++,t)}function c(n){let r=n.attributes;for(let n in r)t.update(r[n],e.ARRAY_BUFFER)}function l(e){let n=[],r=e.index,i=e.attributes.position,o=0;if(i===void 0)return;if(r!==null){let e=r.array;o=r.version;for(let t=0,r=e.length;t<r;t+=3){let r=e[t+0],i=e[t+1],a=e[t+2];n.push(r,i,i,a,a,r)}}else{let e=i.array;o=i.version;for(let t=0,r=e.length/3-1;t<r;t+=3){let e=t+0,r=t+1,i=t+2;n.push(e,r,r,i,i,e)}}let s=new(i.count>=65535?kc:Oc)(n,1);s.version=o;let c=a.get(e);c&&t.remove(c),a.set(e,s)}function u(e){let t=a.get(e);if(t){let n=e.index;n!==null&&t.version<n.version&&l(e)}else l(e);return a.get(e)}return{get:s,update:c,getWireframeAttribute:u}}function up(e,t,n){let r;function i(e){r=e}let a,o;function s(e){a=e.type,o=e.bytesPerElement}function c(t,i){e.drawElements(r,i,a,t*o),n.update(i,r,1)}function l(t,i,s){s!==0&&(e.drawElementsInstanced(r,i,a,t*o,s),n.update(i,r,s))}function u(e,i,o){if(o===0)return;t.get(`WEBGL_multi_draw`).multiDrawElementsWEBGL(r,i,0,a,e,0,o);let s=0;for(let e=0;e<o;e++)s+=i[e];n.update(s,r,1)}this.setMode=i,this.setIndex=s,this.render=c,this.renderInstances=l,this.renderMultiDraw=u}function dp(e){let t={geometries:0,textures:0},n={frame:0,calls:0,triangles:0,points:0,lines:0};function r(t,r,i){switch(n.calls++,r){case e.TRIANGLES:n.triangles+=t/3*i;break;case e.LINES:n.lines+=t/2*i;break;case e.LINE_STRIP:n.lines+=i*(t-1);break;case e.LINE_LOOP:n.lines+=i*t;break;case e.POINTS:n.points+=i*t;break;default:z(`WebGLInfo: Unknown draw mode:`,r);break}}function i(){n.calls=0,n.triangles=0,n.points=0,n.lines=0}return{memory:t,render:n,programs:null,autoReset:!0,reset:i,update:r}}function fp(e,t,n){let r=new WeakMap,i=new ss;function a(a,o,s){let c=a.morphTargetInfluences,l=o.morphAttributes.position||o.morphAttributes.normal||o.morphAttributes.color,u=l===void 0?0:l.length,d=r.get(o);if(d===void 0||d.count!==u){d!==void 0&&d.texture.dispose();let e=o.morphAttributes.position!==void 0,n=o.morphAttributes.normal!==void 0,a=o.morphAttributes.color!==void 0,s=o.morphAttributes.position||[],c=o.morphAttributes.normal||[],l=o.morphAttributes.color||[],f=0;e===!0&&(f=1),n===!0&&(f=2),a===!0&&(f=3);let p=o.attributes.position.count*f,m=1;p>t.maxTextureSize&&(m=Math.ceil(p/t.maxTextureSize),p=t.maxTextureSize);let h=new Float32Array(p*m*4*u),g=new us(h,p,m,u);g.type=Ui,g.needsUpdate=!0;let _=f*4;for(let t=0;t<u;t++){let r=s[t],o=c[t],u=l[t],d=p*m*4*t;for(let t=0;t<r.count;t++){let s=t*_;e===!0&&(i.fromBufferAttribute(r,t),h[d+s+0]=i.x,h[d+s+1]=i.y,h[d+s+2]=i.z,h[d+s+3]=0),n===!0&&(i.fromBufferAttribute(o,t),h[d+s+4]=i.x,h[d+s+5]=i.y,h[d+s+6]=i.z,h[d+s+7]=0),a===!0&&(i.fromBufferAttribute(u,t),h[d+s+8]=i.x,h[d+s+9]=i.y,h[d+s+10]=i.z,h[d+s+11]=u.itemSize===4?i.w:1)}}d={count:u,texture:g,size:new V(p,m)},r.set(o,d);function v(){g.dispose(),r.delete(o),o.removeEventListener(`dispose`,v)}o.addEventListener(`dispose`,v)}if(a.isInstancedMesh===!0&&a.morphTexture!==null)s.getUniforms().setValue(e,`morphTexture`,a.morphTexture,n);else{let t=0;for(let e=0;e<c.length;e++)t+=c[e];let n=o.morphTargetsRelative?1:1-t;s.getUniforms().setValue(e,`morphTargetBaseInfluence`,n),s.getUniforms().setValue(e,`morphTargetInfluences`,c)}s.getUniforms().setValue(e,`morphTargetsTexture`,d.texture,n),s.getUniforms().setValue(e,`morphTargetsTextureSize`,d.size)}return{update:a}}function pp(e,t,n,r,i){let a=new WeakMap;function o(r){let o=i.render.frame,s=r.geometry,l=t.get(r,s);if(a.get(l)!==o&&(t.update(l),a.set(l,o)),r.isInstancedMesh&&(r.hasEventListener(`dispose`,c)===!1&&r.addEventListener(`dispose`,c),a.get(r)!==o&&(n.update(r.instanceMatrix,e.ARRAY_BUFFER),r.instanceColor!==null&&n.update(r.instanceColor,e.ARRAY_BUFFER),a.set(r,o))),r.isSkinnedMesh){let e=r.skeleton;a.get(e)!==o&&(e.update(),a.set(e,o))}return l}function s(){a=new WeakMap}function c(e){let t=e.target;t.removeEventListener(`dispose`,c),r.releaseStatesOfObject(t),n.remove(t.instanceMatrix),t.instanceColor!==null&&n.remove(t.instanceColor)}return{update:o,dispose:s}}var mp={1:`LINEAR_TONE_MAPPING`,2:`REINHARD_TONE_MAPPING`,3:`CINEON_TONE_MAPPING`,4:`ACES_FILMIC_TONE_MAPPING`,6:`AGX_TONE_MAPPING`,7:`NEUTRAL_TONE_MAPPING`,5:`CUSTOM_TONE_MAPPING`};function hp(e,t,n,r,i){let a=new ls(t,n,{type:e,depthBuffer:r,stencilBuffer:i,depthTexture:r?new du(t,n):void 0}),o=new ls(t,n,{type:Wi,depthBuffer:!1,stencilBuffer:!1}),s=new Vc;s.setAttribute(`position`,new G([-1,3,0,-1,-1,0,3,-1,0],3)),s.setAttribute(`uv`,new G([0,2,0,0,2,0],2));let c=new dd({uniforms:{tDiffuse:{value:null}},vertexShader:`
			precision highp float;

			uniform mat4 modelViewMatrix;
			uniform mat4 projectionMatrix;

			attribute vec3 position;
			attribute vec2 uv;

			varying vec2 vUv;

			void main() {
				vUv = uv;
				gl_Position = projectionMatrix * modelViewMatrix * vec4( position, 1.0 );
			}`,fragmentShader:`
			precision highp float;

			uniform sampler2D tDiffuse;

			varying vec2 vUv;

			#include <tonemapping_pars_fragment>
			#include <colorspace_pars_fragment>

			void main() {
				gl_FragColor = texture2D( tDiffuse, vUv );

				#ifdef LINEAR_TONE_MAPPING
					gl_FragColor.rgb = LinearToneMapping( gl_FragColor.rgb );
				#elif defined( REINHARD_TONE_MAPPING )
					gl_FragColor.rgb = ReinhardToneMapping( gl_FragColor.rgb );
				#elif defined( CINEON_TONE_MAPPING )
					gl_FragColor.rgb = CineonToneMapping( gl_FragColor.rgb );
				#elif defined( ACES_FILMIC_TONE_MAPPING )
					gl_FragColor.rgb = ACESFilmicToneMapping( gl_FragColor.rgb );
				#elif defined( AGX_TONE_MAPPING )
					gl_FragColor.rgb = AgXToneMapping( gl_FragColor.rgb );
				#elif defined( NEUTRAL_TONE_MAPPING )
					gl_FragColor.rgb = NeutralToneMapping( gl_FragColor.rgb );
				#elif defined( CUSTOM_TONE_MAPPING )
					gl_FragColor.rgb = CustomToneMapping( gl_FragColor.rgb );
				#endif

				#ifdef SRGB_TRANSFER
					gl_FragColor = sRGBTransferOETF( gl_FragColor );
				#endif
			}`,depthTest:!1,depthWrite:!1}),l=new kl(s,c),u=new Kd(-1,1,1,-1,0,1),d=null,f=null,p=!1,m,h=null,g=[],_=!1;this.setSize=function(e,t){a.setSize(e,t),o.setSize(e,t);for(let n=0;n<g.length;n++){let r=g[n];r.setSize&&r.setSize(e,t)}},this.setEffects=function(e){g=e,_=g.length>0&&g[0].isRenderPass===!0;let t=a.width,n=a.height;for(let e=0;e<g.length;e++){let r=g[e];r.setSize&&r.setSize(t,n)}},this.begin=function(e,t){if(p||e.toneMapping===0&&g.length===0)return!1;if(h=t,t!==null){let e=t.width,n=t.height;(a.width!==e||a.height!==n)&&this.setSize(e,n)}return _===!1&&e.setRenderTarget(a),m=e.toneMapping,e.toneMapping=0,!0},this.hasRenderPass=function(){return _},this.end=function(e,t){e.toneMapping=m,p=!0;let n=a,r=o;for(let i=0;i<g.length;i++){let a=g[i];if(a.enabled!==!1&&(a.render(e,r,n,t),a.needsSwap!==!1)){let e=n;n=r,r=e}}if(d!==e.outputColorSpace||f!==e.toneMapping){d=e.outputColorSpace,f=e.toneMapping,c.defines={},Xo.getTransfer(d)===`srgb`&&(c.defines.SRGB_TRANSFER=``);let t=mp[f];t&&(c.defines[t]=``),c.needsUpdate=!0}c.uniforms.tDiffuse.value=n.texture,e.setRenderTarget(h),e.render(l,u),h=null,p=!1},this.isCompositing=function(){return p},this.dispose=function(){a.depthTexture&&a.depthTexture.dispose(),a.dispose(),o.dispose(),s.dispose(),c.dispose()}}var gp=new os,_p=new du(1,1),vp=new us,yp=new ds,bp=new lu,xp=[],Sp=[],Cp=new Float32Array(16),wp=new Float32Array(9),Tp=new Float32Array(4);function Ep(e,t,n){let r=e[0];if(r<=0||r>0)return e;let i=t*n,a=xp[i];if(a===void 0&&(a=new Float32Array(i),xp[i]=a),t!==0){r.toArray(a,0);for(let r=1,i=0;r!==t;++r)i+=n,e[r].toArray(a,i)}return a}function Dp(e,t){if(e.length!==t.length)return!1;for(let n=0,r=e.length;n<r;n++)if(e[n]!==t[n])return!1;return!0}function Op(e,t){for(let n=0,r=t.length;n<r;n++)e[n]=t[n]}function kp(e,t){let n=Sp[t];n===void 0&&(n=new Int32Array(t),Sp[t]=n);for(let r=0;r!==t;++r)n[r]=e.allocateTextureUnit();return n}function Ap(e,t){let n=this.cache;n[0]!==t&&(e.uniform1f(this.addr,t),n[0]=t)}function jp(e,t){let n=this.cache;if(t.x!==void 0)(n[0]!==t.x||n[1]!==t.y)&&(e.uniform2f(this.addr,t.x,t.y),n[0]=t.x,n[1]=t.y);else{if(Dp(n,t))return;e.uniform2fv(this.addr,t),Op(n,t)}}function Mp(e,t){let n=this.cache;if(t.x!==void 0)(n[0]!==t.x||n[1]!==t.y||n[2]!==t.z)&&(e.uniform3f(this.addr,t.x,t.y,t.z),n[0]=t.x,n[1]=t.y,n[2]=t.z);else if(t.r!==void 0)(n[0]!==t.r||n[1]!==t.g||n[2]!==t.b)&&(e.uniform3f(this.addr,t.r,t.g,t.b),n[0]=t.r,n[1]=t.g,n[2]=t.b);else{if(Dp(n,t))return;e.uniform3fv(this.addr,t),Op(n,t)}}function Np(e,t){let n=this.cache;if(t.x!==void 0)(n[0]!==t.x||n[1]!==t.y||n[2]!==t.z||n[3]!==t.w)&&(e.uniform4f(this.addr,t.x,t.y,t.z,t.w),n[0]=t.x,n[1]=t.y,n[2]=t.z,n[3]=t.w);else{if(Dp(n,t))return;e.uniform4fv(this.addr,t),Op(n,t)}}function Pp(e,t){let n=this.cache,r=t.elements;if(r===void 0){if(Dp(n,t))return;e.uniformMatrix2fv(this.addr,!1,t),Op(n,t)}else{if(Dp(n,r))return;Tp.set(r),e.uniformMatrix2fv(this.addr,!1,Tp),Op(n,r)}}function Fp(e,t){let n=this.cache,r=t.elements;if(r===void 0){if(Dp(n,t))return;e.uniformMatrix3fv(this.addr,!1,t),Op(n,t)}else{if(Dp(n,r))return;wp.set(r),e.uniformMatrix3fv(this.addr,!1,wp),Op(n,r)}}function Ip(e,t){let n=this.cache,r=t.elements;if(r===void 0){if(Dp(n,t))return;e.uniformMatrix4fv(this.addr,!1,t),Op(n,t)}else{if(Dp(n,r))return;Cp.set(r),e.uniformMatrix4fv(this.addr,!1,Cp),Op(n,r)}}function Lp(e,t){let n=this.cache;n[0]!==t&&(e.uniform1i(this.addr,t),n[0]=t)}function Rp(e,t){let n=this.cache;if(t.x!==void 0)(n[0]!==t.x||n[1]!==t.y)&&(e.uniform2i(this.addr,t.x,t.y),n[0]=t.x,n[1]=t.y);else{if(Dp(n,t))return;e.uniform2iv(this.addr,t),Op(n,t)}}function zp(e,t){let n=this.cache;if(t.x!==void 0)(n[0]!==t.x||n[1]!==t.y||n[2]!==t.z)&&(e.uniform3i(this.addr,t.x,t.y,t.z),n[0]=t.x,n[1]=t.y,n[2]=t.z);else{if(Dp(n,t))return;e.uniform3iv(this.addr,t),Op(n,t)}}function Bp(e,t){let n=this.cache;if(t.x!==void 0)(n[0]!==t.x||n[1]!==t.y||n[2]!==t.z||n[3]!==t.w)&&(e.uniform4i(this.addr,t.x,t.y,t.z,t.w),n[0]=t.x,n[1]=t.y,n[2]=t.z,n[3]=t.w);else{if(Dp(n,t))return;e.uniform4iv(this.addr,t),Op(n,t)}}function Vp(e,t){let n=this.cache;n[0]!==t&&(e.uniform1ui(this.addr,t),n[0]=t)}function Hp(e,t){let n=this.cache;if(t.x!==void 0)(n[0]!==t.x||n[1]!==t.y)&&(e.uniform2ui(this.addr,t.x,t.y),n[0]=t.x,n[1]=t.y);else{if(Dp(n,t))return;e.uniform2uiv(this.addr,t),Op(n,t)}}function Up(e,t){let n=this.cache;if(t.x!==void 0)(n[0]!==t.x||n[1]!==t.y||n[2]!==t.z)&&(e.uniform3ui(this.addr,t.x,t.y,t.z),n[0]=t.x,n[1]=t.y,n[2]=t.z);else{if(Dp(n,t))return;e.uniform3uiv(this.addr,t),Op(n,t)}}function Wp(e,t){let n=this.cache;if(t.x!==void 0)(n[0]!==t.x||n[1]!==t.y||n[2]!==t.z||n[3]!==t.w)&&(e.uniform4ui(this.addr,t.x,t.y,t.z,t.w),n[0]=t.x,n[1]=t.y,n[2]=t.z,n[3]=t.w);else{if(Dp(n,t))return;e.uniform4uiv(this.addr,t),Op(n,t)}}function Gp(e,t,n){let r=this.cache,i=n.allocateTextureUnit();r[0]!==i&&(e.uniform1i(this.addr,i),r[0]=i);let a;this.type===e.SAMPLER_2D_SHADOW?(_p.compareFunction=n.isReversedDepthBuffer()?518:515,a=_p):a=gp,n.setTexture2D(t||a,i)}function Kp(e,t,n){let r=this.cache,i=n.allocateTextureUnit();r[0]!==i&&(e.uniform1i(this.addr,i),r[0]=i),n.setTexture3D(t||yp,i)}function qp(e,t,n){let r=this.cache,i=n.allocateTextureUnit();r[0]!==i&&(e.uniform1i(this.addr,i),r[0]=i),n.setTextureCube(t||bp,i)}function Jp(e,t,n){let r=this.cache,i=n.allocateTextureUnit();r[0]!==i&&(e.uniform1i(this.addr,i),r[0]=i),n.setTexture2DArray(t||vp,i)}function Yp(e){switch(e){case 5126:return Ap;case 35664:return jp;case 35665:return Mp;case 35666:return Np;case 35674:return Pp;case 35675:return Fp;case 35676:return Ip;case 5124:case 35670:return Lp;case 35667:case 35671:return Rp;case 35668:case 35672:return zp;case 35669:case 35673:return Bp;case 5125:return Vp;case 36294:return Hp;case 36295:return Up;case 36296:return Wp;case 35678:case 36198:case 36298:case 36306:case 35682:return Gp;case 35679:case 36299:case 36307:return Kp;case 35680:case 36300:case 36308:case 36293:return qp;case 36289:case 36303:case 36311:case 36292:return Jp}}function Xp(e,t){e.uniform1fv(this.addr,t)}function Zp(e,t){let n=Ep(t,this.size,2);e.uniform2fv(this.addr,n)}function Qp(e,t){let n=Ep(t,this.size,3);e.uniform3fv(this.addr,n)}function $p(e,t){let n=Ep(t,this.size,4);e.uniform4fv(this.addr,n)}function em(e,t){let n=Ep(t,this.size,4);e.uniformMatrix2fv(this.addr,!1,n)}function tm(e,t){let n=Ep(t,this.size,9);e.uniformMatrix3fv(this.addr,!1,n)}function nm(e,t){let n=Ep(t,this.size,16);e.uniformMatrix4fv(this.addr,!1,n)}function rm(e,t){e.uniform1iv(this.addr,t)}function im(e,t){e.uniform2iv(this.addr,t)}function am(e,t){e.uniform3iv(this.addr,t)}function om(e,t){e.uniform4iv(this.addr,t)}function sm(e,t){e.uniform1uiv(this.addr,t)}function cm(e,t){e.uniform2uiv(this.addr,t)}function lm(e,t){e.uniform3uiv(this.addr,t)}function um(e,t){e.uniform4uiv(this.addr,t)}function dm(e,t,n){let r=this.cache,i=t.length,a=kp(n,i);Dp(r,a)||(e.uniform1iv(this.addr,a),Op(r,a));let o;o=this.type===e.SAMPLER_2D_SHADOW?_p:gp;for(let e=0;e!==i;++e)n.setTexture2D(t[e]||o,a[e])}function fm(e,t,n){let r=this.cache,i=t.length,a=kp(n,i);Dp(r,a)||(e.uniform1iv(this.addr,a),Op(r,a));for(let e=0;e!==i;++e)n.setTexture3D(t[e]||yp,a[e])}function pm(e,t,n){let r=this.cache,i=t.length,a=kp(n,i);Dp(r,a)||(e.uniform1iv(this.addr,a),Op(r,a));for(let e=0;e!==i;++e)n.setTextureCube(t[e]||bp,a[e])}function mm(e,t,n){let r=this.cache,i=t.length,a=kp(n,i);Dp(r,a)||(e.uniform1iv(this.addr,a),Op(r,a));for(let e=0;e!==i;++e)n.setTexture2DArray(t[e]||vp,a[e])}function hm(e){switch(e){case 5126:return Xp;case 35664:return Zp;case 35665:return Qp;case 35666:return $p;case 35674:return em;case 35675:return tm;case 35676:return nm;case 5124:case 35670:return rm;case 35667:case 35671:return im;case 35668:case 35672:return am;case 35669:case 35673:return om;case 5125:return sm;case 36294:return cm;case 36295:return lm;case 36296:return um;case 35678:case 36198:case 36298:case 36306:case 35682:return dm;case 35679:case 36299:case 36307:return fm;case 35680:case 36300:case 36308:case 36293:return pm;case 36289:case 36303:case 36311:case 36292:return mm}}var gm=class{constructor(e,t,n){this.id=e,this.addr=n,this.cache=[],this.type=t.type,this.setValue=Yp(t.type)}},_m=class{constructor(e,t,n){this.id=e,this.addr=n,this.cache=[],this.type=t.type,this.size=t.size,this.setValue=hm(t.type)}},vm=class{constructor(e){this.id=e,this.seq=[],this.map={}}setValue(e,t,n){let r=this.seq;for(let i=0,a=r.length;i!==a;++i){let a=r[i];a.setValue(e,t[a.id],n)}}},ym=/(\w+)(\])?(\[|\.)?/g;function bm(e,t){e.seq.push(t),e.map[t.id]=t}function xm(e,t,n){let r=e.name,i=r.length;for(ym.lastIndex=0;;){let a=ym.exec(r),o=ym.lastIndex,s=a[1],c=a[2]===`]`,l=a[3];if(c&&(s|=0),l===void 0||l===`[`&&o+2===i){bm(n,l===void 0?new gm(s,e,t):new _m(s,e,t));break}else{let e=n.map[s];e===void 0&&(e=new vm(s),bm(n,e)),n=e}}}var Sm=class{constructor(e,t){this.seq=[],this.map={};let n=e.getProgramParameter(t,e.ACTIVE_UNIFORMS);for(let r=0;r<n;++r){let n=e.getActiveUniform(t,r);xm(n,e.getUniformLocation(t,n.name),this)}let r=[],i=[];for(let t of this.seq)t.type===e.SAMPLER_2D_SHADOW||t.type===e.SAMPLER_CUBE_SHADOW||t.type===e.SAMPLER_2D_ARRAY_SHADOW?r.push(t):i.push(t);r.length>0&&(this.seq=r.concat(i))}setValue(e,t,n,r){let i=this.map[t];i!==void 0&&i.setValue(e,n,r)}setOptional(e,t,n){let r=t[n];r!==void 0&&this.setValue(e,n,r)}static upload(e,t,n,r){for(let i=0,a=t.length;i!==a;++i){let a=t[i],o=n[a.id];o.needsUpdate!==!1&&a.setValue(e,o.value,r)}}static seqWithValue(e,t){let n=[];for(let r=0,i=e.length;r!==i;++r){let i=e[r];i.id in t&&n.push(i)}return n}};function Cm(e,t,n){let r=e.createShader(t);return e.shaderSource(r,n),e.compileShader(r),r}var wm=37297,Tm=0;function Em(e,t){let n=e.split(`
`),r=[],i=Math.max(t-6,0),a=Math.min(t+6,n.length);for(let e=i;e<a;e++){let i=e+1;r.push(`${i===t?`>`:` `} ${i}: ${n[e]}`)}return r.join(`
`)}var Dm=new U;function Om(e){Xo._getMatrix(Dm,Xo.workingColorSpace,e);let t=`mat3( ${Dm.elements.map(e=>e.toFixed(4))} )`;switch(Xo.getTransfer(e)){case $a:return[t,`LinearTransferOETF`];case eo:return[t,`sRGBTransferOETF`];default:return R(`WebGLProgram: Unsupported color space: `,e),[t,`LinearTransferOETF`]}}function km(e,t,n){let r=e.getShaderParameter(t,e.COMPILE_STATUS),i=(e.getShaderInfoLog(t)||``).trim();if(r&&i===``)return``;let a=/ERROR: 0:(\d+)/.exec(i);if(a){let r=parseInt(a[1]);return n.toUpperCase()+`

`+i+`

`+Em(e.getShaderSource(t),r)}else return i}function Am(e,t){let n=Om(t);return[`vec4 ${e}( vec4 value ) {`,`	return ${n[1]}( vec4( value.rgb * ${n[0]}, value.a ) );`,`}`].join(`
`)}var jm={1:`Linear`,2:`Reinhard`,3:`Cineon`,4:`ACESFilmic`,6:`AgX`,7:`Neutral`,5:`Custom`};function Mm(e,t){let n=jm[t];return n===void 0?(R(`WebGLProgram: Unsupported toneMapping:`,t),`vec3 `+e+`( vec3 color ) { return LinearToneMapping( color ); }`):`vec3 `+e+`( vec3 color ) { return `+n+`ToneMapping( color ); }`}var Nm=new H;function Pm(){return Xo.getLuminanceCoefficients(Nm),[`float luminance( const in vec3 rgb ) {`,`	const vec3 weights = vec3( ${Nm.x.toFixed(4)}, ${Nm.y.toFixed(4)}, ${Nm.z.toFixed(4)} );`,`	return dot( weights, rgb );`,`}`].join(`
`)}function Fm(e){return[e.extensionClipCullDistance?`#extension GL_ANGLE_clip_cull_distance : require`:``,e.extensionMultiDraw?`#extension GL_ANGLE_multi_draw : require`:``].filter(Rm).join(`
`)}function Im(e){let t=[];for(let n in e){let r=e[n];r!==!1&&t.push(`#define `+n+` `+r)}return t.join(`
`)}function Lm(e,t){let n={},r=e.getProgramParameter(t,e.ACTIVE_ATTRIBUTES);for(let i=0;i<r;i++){let r=e.getActiveAttrib(t,i),a=r.name,o=1;r.type===e.FLOAT_MAT2&&(o=2),r.type===e.FLOAT_MAT3&&(o=3),r.type===e.FLOAT_MAT4&&(o=4),n[a]={type:r.type,location:e.getAttribLocation(t,a),locationSize:o}}return n}function Rm(e){return e!==``}function zm(e,t){let n=t.numSpotLightShadows+t.numSpotLightMaps-t.numSpotLightShadowsWithMaps;return e.replace(/NUM_DIR_LIGHTS/g,t.numDirLights).replace(/NUM_SPOT_LIGHTS/g,t.numSpotLights).replace(/NUM_SPOT_LIGHT_MAPS/g,t.numSpotLightMaps).replace(/NUM_SPOT_LIGHT_COORDS/g,n).replace(/NUM_RECT_AREA_LIGHTS/g,t.numRectAreaLights).replace(/NUM_POINT_LIGHTS/g,t.numPointLights).replace(/NUM_HEMI_LIGHTS/g,t.numHemiLights).replace(/NUM_DIR_LIGHT_SHADOWS/g,t.numDirLightShadows).replace(/NUM_SPOT_LIGHT_SHADOWS_WITH_MAPS/g,t.numSpotLightShadowsWithMaps).replace(/NUM_SPOT_LIGHT_SHADOWS/g,t.numSpotLightShadows).replace(/NUM_POINT_LIGHT_SHADOWS/g,t.numPointLightShadows)}function Bm(e,t){return e.replace(/NUM_CLIPPING_PLANES/g,t.numClippingPlanes).replace(/UNION_CLIPPING_PLANES/g,t.numClippingPlanes-t.numClipIntersection)}var Vm=/^[ \t]*#include +<([\w\d./]+)>/gm;function Hm(e){return e.replace(Vm,Wm)}var Um=new Map;function Wm(e,t){let n=K[t];if(n===void 0){let e=Um.get(t);if(e!==void 0)n=K[e],R(`WebGLRenderer: Shader chunk "%s" has been deprecated. Use "%s" instead.`,t,e);else throw Error(`Can not resolve #include <`+t+`>`)}return Hm(n)}var Gm=/#pragma unroll_loop_start\s+for\s*\(\s*int\s+i\s*=\s*(\d+)\s*;\s*i\s*<\s*(\d+)\s*;\s*i\s*\+\+\s*\)\s*{([\s\S]+?)}\s+#pragma unroll_loop_end/g;function Km(e){return e.replace(Gm,qm)}function qm(e,t,n,r){let i=``;for(let e=parseInt(t);e<parseInt(n);e++)i+=r.replace(/\[\s*i\s*\]/g,`[ `+e+` ]`).replace(/UNROLLED_LOOP_INDEX/g,e);return i}function Jm(e){let t=`precision ${e.precision} float;
	precision ${e.precision} int;
	precision ${e.precision} sampler2D;
	precision ${e.precision} samplerCube;
	precision ${e.precision} sampler3D;
	precision ${e.precision} sampler2DArray;
	precision ${e.precision} sampler2DShadow;
	precision ${e.precision} samplerCubeShadow;
	precision ${e.precision} sampler2DArrayShadow;
	precision ${e.precision} isampler2D;
	precision ${e.precision} isampler3D;
	precision ${e.precision} isamplerCube;
	precision ${e.precision} isampler2DArray;
	precision ${e.precision} usampler2D;
	precision ${e.precision} usampler3D;
	precision ${e.precision} usamplerCube;
	precision ${e.precision} usampler2DArray;
	`;return e.precision===`highp`?t+=`
#define HIGH_PRECISION`:e.precision===`mediump`?t+=`
#define MEDIUM_PRECISION`:e.precision===`lowp`&&(t+=`
#define LOW_PRECISION`),t}var Ym={1:`SHADOWMAP_TYPE_PCF`,3:`SHADOWMAP_TYPE_VSM`};function Xm(e){return Ym[e.shadowMapType]||`SHADOWMAP_TYPE_BASIC`}var Zm={301:`ENVMAP_TYPE_CUBE`,302:`ENVMAP_TYPE_CUBE`,306:`ENVMAP_TYPE_CUBE_UV`};function Qm(e){return e.envMap===!1?`ENVMAP_TYPE_CUBE`:Zm[e.envMapMode]||`ENVMAP_TYPE_CUBE`}var $m={302:`ENVMAP_MODE_REFRACTION`};function eh(e){return e.envMap===!1?`ENVMAP_MODE_REFLECTION`:$m[e.envMapMode]||`ENVMAP_MODE_REFLECTION`}var th={0:`ENVMAP_BLENDING_MULTIPLY`,1:`ENVMAP_BLENDING_MIX`,2:`ENVMAP_BLENDING_ADD`};function nh(e){return e.envMap===!1?`ENVMAP_BLENDING_NONE`:th[e.combine]||`ENVMAP_BLENDING_NONE`}function rh(e){let t=e.envMapCubeUVHeight;if(t===null)return null;let n=Math.log2(t)-2,r=1/t;return{texelWidth:1/(3*Math.max(2**n,112)),texelHeight:r,maxMip:n}}function ih(e,t,n,r){let i=e.getContext(),a=n.defines,o=n.vertexShader,s=n.fragmentShader,c=Xm(n),l=Qm(n),u=eh(n),d=nh(n),f=rh(n),p=Fm(n),m=Im(a),h=i.createProgram(),g,_,v=n.glslVersion?`#version `+n.glslVersion+`
`:``;n.isRawShaderMaterial?(g=[`#define SHADER_TYPE `+n.shaderType,`#define SHADER_NAME `+n.shaderName,m].filter(Rm).join(`
`),g.length>0&&(g+=`
`),_=[`#define SHADER_TYPE `+n.shaderType,`#define SHADER_NAME `+n.shaderName,m].filter(Rm).join(`
`),_.length>0&&(_+=`
`)):(g=[Jm(n),`#define SHADER_TYPE `+n.shaderType,`#define SHADER_NAME `+n.shaderName,m,n.extensionClipCullDistance?`#define USE_CLIP_DISTANCE`:``,n.batching?`#define USE_BATCHING`:``,n.batchingColor?`#define USE_BATCHING_COLOR`:``,n.instancing?`#define USE_INSTANCING`:``,n.instancingColor?`#define USE_INSTANCING_COLOR`:``,n.instancingMorph?`#define USE_INSTANCING_MORPH`:``,n.useFog&&n.fog?`#define USE_FOG`:``,n.useFog&&n.fogExp2?`#define FOG_EXP2`:``,n.map?`#define USE_MAP`:``,n.envMap?`#define USE_ENVMAP`:``,n.envMap?`#define `+u:``,n.lightMap?`#define USE_LIGHTMAP`:``,n.aoMap?`#define USE_AOMAP`:``,n.bumpMap?`#define USE_BUMPMAP`:``,n.normalMap?`#define USE_NORMALMAP`:``,n.normalMapObjectSpace?`#define USE_NORMALMAP_OBJECTSPACE`:``,n.normalMapTangentSpace?`#define USE_NORMALMAP_TANGENTSPACE`:``,n.displacementMap?`#define USE_DISPLACEMENTMAP`:``,n.emissiveMap?`#define USE_EMISSIVEMAP`:``,n.anisotropy?`#define USE_ANISOTROPY`:``,n.anisotropyMap?`#define USE_ANISOTROPYMAP`:``,n.clearcoatMap?`#define USE_CLEARCOATMAP`:``,n.clearcoatRoughnessMap?`#define USE_CLEARCOAT_ROUGHNESSMAP`:``,n.clearcoatNormalMap?`#define USE_CLEARCOAT_NORMALMAP`:``,n.iridescenceMap?`#define USE_IRIDESCENCEMAP`:``,n.iridescenceThicknessMap?`#define USE_IRIDESCENCE_THICKNESSMAP`:``,n.specularMap?`#define USE_SPECULARMAP`:``,n.specularColorMap?`#define USE_SPECULAR_COLORMAP`:``,n.specularIntensityMap?`#define USE_SPECULAR_INTENSITYMAP`:``,n.roughnessMap?`#define USE_ROUGHNESSMAP`:``,n.metalnessMap?`#define USE_METALNESSMAP`:``,n.alphaMap?`#define USE_ALPHAMAP`:``,n.alphaHash?`#define USE_ALPHAHASH`:``,n.transmission?`#define USE_TRANSMISSION`:``,n.transmissionMap?`#define USE_TRANSMISSIONMAP`:``,n.thicknessMap?`#define USE_THICKNESSMAP`:``,n.sheenColorMap?`#define USE_SHEEN_COLORMAP`:``,n.sheenRoughnessMap?`#define USE_SHEEN_ROUGHNESSMAP`:``,n.mapUv?`#define MAP_UV `+n.mapUv:``,n.alphaMapUv?`#define ALPHAMAP_UV `+n.alphaMapUv:``,n.lightMapUv?`#define LIGHTMAP_UV `+n.lightMapUv:``,n.aoMapUv?`#define AOMAP_UV `+n.aoMapUv:``,n.emissiveMapUv?`#define EMISSIVEMAP_UV `+n.emissiveMapUv:``,n.bumpMapUv?`#define BUMPMAP_UV `+n.bumpMapUv:``,n.normalMapUv?`#define NORMALMAP_UV `+n.normalMapUv:``,n.displacementMapUv?`#define DISPLACEMENTMAP_UV `+n.displacementMapUv:``,n.metalnessMapUv?`#define METALNESSMAP_UV `+n.metalnessMapUv:``,n.roughnessMapUv?`#define ROUGHNESSMAP_UV `+n.roughnessMapUv:``,n.anisotropyMapUv?`#define ANISOTROPYMAP_UV `+n.anisotropyMapUv:``,n.clearcoatMapUv?`#define CLEARCOATMAP_UV `+n.clearcoatMapUv:``,n.clearcoatNormalMapUv?`#define CLEARCOAT_NORMALMAP_UV `+n.clearcoatNormalMapUv:``,n.clearcoatRoughnessMapUv?`#define CLEARCOAT_ROUGHNESSMAP_UV `+n.clearcoatRoughnessMapUv:``,n.iridescenceMapUv?`#define IRIDESCENCEMAP_UV `+n.iridescenceMapUv:``,n.iridescenceThicknessMapUv?`#define IRIDESCENCE_THICKNESSMAP_UV `+n.iridescenceThicknessMapUv:``,n.sheenColorMapUv?`#define SHEEN_COLORMAP_UV `+n.sheenColorMapUv:``,n.sheenRoughnessMapUv?`#define SHEEN_ROUGHNESSMAP_UV `+n.sheenRoughnessMapUv:``,n.specularMapUv?`#define SPECULARMAP_UV `+n.specularMapUv:``,n.specularColorMapUv?`#define SPECULAR_COLORMAP_UV `+n.specularColorMapUv:``,n.specularIntensityMapUv?`#define SPECULAR_INTENSITYMAP_UV `+n.specularIntensityMapUv:``,n.transmissionMapUv?`#define TRANSMISSIONMAP_UV `+n.transmissionMapUv:``,n.thicknessMapUv?`#define THICKNESSMAP_UV `+n.thicknessMapUv:``,n.vertexTangents&&n.flatShading===!1?`#define USE_TANGENT`:``,n.vertexNormals?`#define HAS_NORMAL`:``,n.vertexColors?`#define USE_COLOR`:``,n.vertexAlphas?`#define USE_COLOR_ALPHA`:``,n.vertexUv1s?`#define USE_UV1`:``,n.vertexUv2s?`#define USE_UV2`:``,n.vertexUv3s?`#define USE_UV3`:``,n.pointsUvs?`#define USE_POINTS_UV`:``,n.flatShading?`#define FLAT_SHADED`:``,n.skinning?`#define USE_SKINNING`:``,n.morphTargets?`#define USE_MORPHTARGETS`:``,n.morphNormals&&n.flatShading===!1?`#define USE_MORPHNORMALS`:``,n.morphColors?`#define USE_MORPHCOLORS`:``,n.morphTargetsCount>0?`#define MORPHTARGETS_TEXTURE_STRIDE `+n.morphTextureStride:``,n.morphTargetsCount>0?`#define MORPHTARGETS_COUNT `+n.morphTargetsCount:``,n.doubleSided?`#define DOUBLE_SIDED`:``,n.flipSided?`#define FLIP_SIDED`:``,n.shadowMapEnabled?`#define USE_SHADOWMAP`:``,n.shadowMapEnabled?`#define `+c:``,n.sizeAttenuation?`#define USE_SIZEATTENUATION`:``,n.numLightProbes>0?`#define USE_LIGHT_PROBES`:``,n.logarithmicDepthBuffer?`#define USE_LOGARITHMIC_DEPTH_BUFFER`:``,n.reversedDepthBuffer?`#define USE_REVERSED_DEPTH_BUFFER`:``,`uniform mat4 modelMatrix;`,`uniform mat4 modelViewMatrix;`,`uniform mat4 projectionMatrix;`,`uniform mat4 viewMatrix;`,`uniform mat3 normalMatrix;`,`uniform vec3 cameraPosition;`,`uniform bool isOrthographic;`,`#ifdef USE_INSTANCING`,`	attribute mat4 instanceMatrix;`,`#endif`,`#ifdef USE_INSTANCING_COLOR`,`	attribute vec3 instanceColor;`,`#endif`,`#ifdef USE_INSTANCING_MORPH`,`	uniform sampler2D morphTexture;`,`#endif`,`attribute vec3 position;`,`attribute vec3 normal;`,`attribute vec2 uv;`,`#ifdef USE_UV1`,`	attribute vec2 uv1;`,`#endif`,`#ifdef USE_UV2`,`	attribute vec2 uv2;`,`#endif`,`#ifdef USE_UV3`,`	attribute vec2 uv3;`,`#endif`,`#ifdef USE_TANGENT`,`	attribute vec4 tangent;`,`#endif`,`#if defined( USE_COLOR_ALPHA )`,`	attribute vec4 color;`,`#elif defined( USE_COLOR )`,`	attribute vec3 color;`,`#endif`,`#ifdef USE_SKINNING`,`	attribute vec4 skinIndex;`,`	attribute vec4 skinWeight;`,`#endif`,`
`].filter(Rm).join(`
`),_=[Jm(n),`#define SHADER_TYPE `+n.shaderType,`#define SHADER_NAME `+n.shaderName,m,n.useFog&&n.fog?`#define USE_FOG`:``,n.useFog&&n.fogExp2?`#define FOG_EXP2`:``,n.alphaToCoverage?`#define ALPHA_TO_COVERAGE`:``,n.map?`#define USE_MAP`:``,n.matcap?`#define USE_MATCAP`:``,n.envMap?`#define USE_ENVMAP`:``,n.envMap?`#define `+l:``,n.envMap?`#define `+u:``,n.envMap?`#define `+d:``,f?`#define CUBEUV_TEXEL_WIDTH `+f.texelWidth:``,f?`#define CUBEUV_TEXEL_HEIGHT `+f.texelHeight:``,f?`#define CUBEUV_MAX_MIP `+f.maxMip+`.0`:``,n.lightMap?`#define USE_LIGHTMAP`:``,n.aoMap?`#define USE_AOMAP`:``,n.bumpMap?`#define USE_BUMPMAP`:``,n.normalMap?`#define USE_NORMALMAP`:``,n.normalMapObjectSpace?`#define USE_NORMALMAP_OBJECTSPACE`:``,n.normalMapTangentSpace?`#define USE_NORMALMAP_TANGENTSPACE`:``,n.packedNormalMap?`#define USE_PACKED_NORMALMAP`:``,n.emissiveMap?`#define USE_EMISSIVEMAP`:``,n.anisotropy?`#define USE_ANISOTROPY`:``,n.anisotropyMap?`#define USE_ANISOTROPYMAP`:``,n.clearcoat?`#define USE_CLEARCOAT`:``,n.clearcoatMap?`#define USE_CLEARCOATMAP`:``,n.clearcoatRoughnessMap?`#define USE_CLEARCOAT_ROUGHNESSMAP`:``,n.clearcoatNormalMap?`#define USE_CLEARCOAT_NORMALMAP`:``,n.dispersion?`#define USE_DISPERSION`:``,n.iridescence?`#define USE_IRIDESCENCE`:``,n.iridescenceMap?`#define USE_IRIDESCENCEMAP`:``,n.iridescenceThicknessMap?`#define USE_IRIDESCENCE_THICKNESSMAP`:``,n.specularMap?`#define USE_SPECULARMAP`:``,n.specularColorMap?`#define USE_SPECULAR_COLORMAP`:``,n.specularIntensityMap?`#define USE_SPECULAR_INTENSITYMAP`:``,n.roughnessMap?`#define USE_ROUGHNESSMAP`:``,n.metalnessMap?`#define USE_METALNESSMAP`:``,n.alphaMap?`#define USE_ALPHAMAP`:``,n.alphaTest?`#define USE_ALPHATEST`:``,n.alphaHash?`#define USE_ALPHAHASH`:``,n.sheen?`#define USE_SHEEN`:``,n.sheenColorMap?`#define USE_SHEEN_COLORMAP`:``,n.sheenRoughnessMap?`#define USE_SHEEN_ROUGHNESSMAP`:``,n.transmission?`#define USE_TRANSMISSION`:``,n.transmissionMap?`#define USE_TRANSMISSIONMAP`:``,n.thicknessMap?`#define USE_THICKNESSMAP`:``,n.vertexTangents&&n.flatShading===!1?`#define USE_TANGENT`:``,n.vertexColors||n.instancingColor?`#define USE_COLOR`:``,n.vertexAlphas||n.batchingColor?`#define USE_COLOR_ALPHA`:``,n.vertexUv1s?`#define USE_UV1`:``,n.vertexUv2s?`#define USE_UV2`:``,n.vertexUv3s?`#define USE_UV3`:``,n.pointsUvs?`#define USE_POINTS_UV`:``,n.gradientMap?`#define USE_GRADIENTMAP`:``,n.flatShading?`#define FLAT_SHADED`:``,n.doubleSided?`#define DOUBLE_SIDED`:``,n.flipSided?`#define FLIP_SIDED`:``,n.shadowMapEnabled?`#define USE_SHADOWMAP`:``,n.shadowMapEnabled?`#define `+c:``,n.premultipliedAlpha?`#define PREMULTIPLIED_ALPHA`:``,n.numLightProbes>0?`#define USE_LIGHT_PROBES`:``,n.numLightProbeGrids>0?`#define USE_LIGHT_PROBES_GRID`:``,n.decodeVideoTexture?`#define DECODE_VIDEO_TEXTURE`:``,n.decodeVideoTextureEmissive?`#define DECODE_VIDEO_TEXTURE_EMISSIVE`:``,n.logarithmicDepthBuffer?`#define USE_LOGARITHMIC_DEPTH_BUFFER`:``,n.reversedDepthBuffer?`#define USE_REVERSED_DEPTH_BUFFER`:``,`uniform mat4 viewMatrix;`,`uniform vec3 cameraPosition;`,`uniform bool isOrthographic;`,n.toneMapping===0?``:`#define TONE_MAPPING`,n.toneMapping===0?``:K.tonemapping_pars_fragment,n.toneMapping===0?``:Mm(`toneMapping`,n.toneMapping),n.dithering?`#define DITHERING`:``,n.opaque?`#define OPAQUE`:``,K.colorspace_pars_fragment,Am(`linearToOutputTexel`,n.outputColorSpace),Pm(),n.useDepthPacking?`#define DEPTH_PACKING `+n.depthPacking:``,`
`].filter(Rm).join(`
`)),o=Hm(o),o=zm(o,n),o=Bm(o,n),s=Hm(s),s=zm(s,n),s=Bm(s,n),o=Km(o),s=Km(s),n.isRawShaderMaterial!==!0&&(v=`#version 300 es
`,g=[p,`#define attribute in`,`#define varying out`,`#define texture2D texture`].join(`
`)+`
`+g,_=[`#define varying in`,n.glslVersion===`300 es`?``:`layout(location = 0) out highp vec4 pc_fragColor;`,n.glslVersion===`300 es`?``:`#define gl_FragColor pc_fragColor`,`#define gl_FragDepthEXT gl_FragDepth`,`#define texture2D texture`,`#define textureCube texture`,`#define texture2DProj textureProj`,`#define texture2DLodEXT textureLod`,`#define texture2DProjLodEXT textureProjLod`,`#define textureCubeLodEXT textureLod`,`#define texture2DGradEXT textureGrad`,`#define texture2DProjGradEXT textureProjGrad`,`#define textureCubeGradEXT textureGrad`].join(`
`)+`
`+_);let y=v+g+o,b=v+_+s,x=Cm(i,i.VERTEX_SHADER,y),S=Cm(i,i.FRAGMENT_SHADER,b);i.attachShader(h,x),i.attachShader(h,S),n.index0AttributeName===void 0?n.morphTargets===!0&&i.bindAttribLocation(h,0,`position`):i.bindAttribLocation(h,0,n.index0AttributeName),i.linkProgram(h);function C(t){if(e.debug.checkShaderErrors){let n=i.getProgramInfoLog(h)||``,r=i.getShaderInfoLog(x)||``,a=i.getShaderInfoLog(S)||``,o=n.trim(),s=r.trim(),c=a.trim(),l=!0,u=!0;if(i.getProgramParameter(h,i.LINK_STATUS)===!1)if(l=!1,typeof e.debug.onShaderError==`function`)e.debug.onShaderError(i,h,x,S);else{let e=km(i,x,`vertex`),n=km(i,S,`fragment`);z(`THREE.WebGLProgram: Shader Error `+i.getError()+` - VALIDATE_STATUS `+i.getProgramParameter(h,i.VALIDATE_STATUS)+`

Material Name: `+t.name+`
Material Type: `+t.type+`

Program Info Log: `+o+`
`+e+`
`+n)}else o===``?(s===``||c===``)&&(u=!1):R(`WebGLProgram: Program Info Log:`,o);u&&(t.diagnostics={runnable:l,programLog:o,vertexShader:{log:s,prefix:g},fragmentShader:{log:c,prefix:_}})}i.deleteShader(x),i.deleteShader(S),w=new Sm(i,h),T=Lm(i,h)}let w;this.getUniforms=function(){return w===void 0&&C(this),w};let T;this.getAttributes=function(){return T===void 0&&C(this),T};let E=n.rendererExtensionParallelShaderCompile===!1;return this.isReady=function(){return E===!1&&(E=i.getProgramParameter(h,wm)),E},this.destroy=function(){r.releaseStatesOfProgram(this),i.deleteProgram(h),this.program=void 0},this.type=n.shaderType,this.name=n.shaderName,this.id=Tm++,this.cacheKey=t,this.usedTimes=1,this.program=h,this.vertexShader=x,this.fragmentShader=S,this}var ah=0,oh=class{constructor(){this.shaderCache=new Map,this.materialCache=new Map}update(e){let t=e.vertexShader,n=e.fragmentShader,r=this._getShaderStage(t),i=this._getShaderStage(n),a=this._getShaderCacheForMaterial(e);return a.has(r)===!1&&(a.add(r),r.usedTimes++),a.has(i)===!1&&(a.add(i),i.usedTimes++),this}remove(e){let t=this.materialCache.get(e);for(let e of t)e.usedTimes--,e.usedTimes===0&&this.shaderCache.delete(e.code);return this.materialCache.delete(e),this}getVertexShaderID(e){return this._getShaderStage(e.vertexShader).id}getFragmentShaderID(e){return this._getShaderStage(e.fragmentShader).id}dispose(){this.shaderCache.clear(),this.materialCache.clear()}_getShaderCacheForMaterial(e){let t=this.materialCache,n=t.get(e);return n===void 0&&(n=new Set,t.set(e,n)),n}_getShaderStage(e){let t=this.shaderCache,n=t.get(e);return n===void 0&&(n=new sh(e),t.set(e,n)),n}},sh=class{constructor(e){this.id=ah++,this.code=e,this.usedTimes=0}};function ch(e){return e===1030||e===37490||e===36285}function lh(e,t,n,r,i,a){let o=new Cs,s=new oh,c=new Set,l=[],u=new Map,d=r.logarithmicDepthBuffer,f=r.precision,p={MeshDepthMaterial:`depth`,MeshDistanceMaterial:`distance`,MeshNormalMaterial:`normal`,MeshBasicMaterial:`basic`,MeshLambertMaterial:`lambert`,MeshPhongMaterial:`phong`,MeshToonMaterial:`toon`,MeshStandardMaterial:`physical`,MeshPhysicalMaterial:`physical`,MeshMatcapMaterial:`matcap`,LineBasicMaterial:`basic`,LineDashedMaterial:`dashed`,PointsMaterial:`points`,ShadowMaterial:`shadow`,SpriteMaterial:`sprite`};function m(e){return c.add(e),e===0?`uv`:`uv${e}`}function h(i,o,l,u,h,g){let _=u.fog,v=h.geometry,y=i.isMeshStandardMaterial||i.isMeshLambertMaterial||i.isMeshPhongMaterial?u.environment:null,b=i.isMeshStandardMaterial||i.isMeshLambertMaterial&&!i.envMap||i.isMeshPhongMaterial&&!i.envMap,x=t.get(i.envMap||y,b),S=x&&x.mapping===306?x.image.height:null,C=p[i.type];i.precision!==null&&(f=r.getMaxPrecision(i.precision),f!==i.precision&&R(`WebGLProgram.getParameters:`,i.precision,`not supported, using`,f,`instead.`));let w=v.morphAttributes.position||v.morphAttributes.normal||v.morphAttributes.color,T=w===void 0?0:w.length,E=0;v.morphAttributes.position!==void 0&&(E=1),v.morphAttributes.normal!==void 0&&(E=2),v.morphAttributes.color!==void 0&&(E=3);let D,O,k,A;if(C){let e=jf[C];D=e.vertexShader,O=e.fragmentShader}else D=i.vertexShader,O=i.fragmentShader,s.update(i),k=s.getVertexShaderID(i),A=s.getFragmentShaderID(i);let ee=e.getRenderTarget(),te=e.state.buffers.depth.getReversed(),j=h.isInstancedMesh===!0,ne=h.isBatchedMesh===!0,M=!!i.map,re=!!i.matcap,N=!!x,ie=!!i.aoMap,ae=!!i.lightMap,oe=!!i.bumpMap,se=!!i.normalMap,ce=!!i.displacementMap,le=!!i.emissiveMap,ue=!!i.metalnessMap,de=!!i.roughnessMap,fe=i.anisotropy>0,pe=i.clearcoat>0,me=i.dispersion>0,he=i.iridescence>0,ge=i.sheen>0,_e=i.transmission>0,ve=fe&&!!i.anisotropyMap,ye=pe&&!!i.clearcoatMap,be=pe&&!!i.clearcoatNormalMap,P=pe&&!!i.clearcoatRoughnessMap,xe=he&&!!i.iridescenceMap,Se=he&&!!i.iridescenceThicknessMap,Ce=ge&&!!i.sheenColorMap,F=ge&&!!i.sheenRoughnessMap,we=!!i.specularMap,I=!!i.specularColorMap,L=!!i.specularIntensityMap,Te=_e&&!!i.transmissionMap,Ee=_e&&!!i.thicknessMap,De=!!i.gradientMap,Oe=!!i.alphaMap,ke=i.alphaTest>0,Ae=!!i.alphaHash,je=!!i.extensions,Me=0;i.toneMapped&&(ee===null||ee.isXRRenderTarget===!0)&&(Me=e.toneMapping);let Ne={shaderID:C,shaderType:i.type,shaderName:i.name,vertexShader:D,fragmentShader:O,defines:i.defines,customVertexShaderID:k,customFragmentShaderID:A,isRawShaderMaterial:i.isRawShaderMaterial===!0,glslVersion:i.glslVersion,precision:f,batching:ne,batchingColor:ne&&h._colorsTexture!==null,instancing:j,instancingColor:j&&h.instanceColor!==null,instancingMorph:j&&h.morphTexture!==null,outputColorSpace:ee===null?e.outputColorSpace:ee.isXRRenderTarget===!0?ee.texture.colorSpace:Xo.workingColorSpace,alphaToCoverage:!!i.alphaToCoverage,map:M,matcap:re,envMap:N,envMapMode:N&&x.mapping,envMapCubeUVHeight:S,aoMap:ie,lightMap:ae,bumpMap:oe,normalMap:se,displacementMap:ce,emissiveMap:le,normalMapObjectSpace:se&&i.normalMapType===1,normalMapTangentSpace:se&&i.normalMapType===0,packedNormalMap:se&&i.normalMapType===0&&ch(i.normalMap.format),metalnessMap:ue,roughnessMap:de,anisotropy:fe,anisotropyMap:ve,clearcoat:pe,clearcoatMap:ye,clearcoatNormalMap:be,clearcoatRoughnessMap:P,dispersion:me,iridescence:he,iridescenceMap:xe,iridescenceThicknessMap:Se,sheen:ge,sheenColorMap:Ce,sheenRoughnessMap:F,specularMap:we,specularColorMap:I,specularIntensityMap:L,transmission:_e,transmissionMap:Te,thicknessMap:Ee,gradientMap:De,opaque:i.transparent===!1&&i.blending===1&&i.alphaToCoverage===!1,alphaMap:Oe,alphaTest:ke,alphaHash:Ae,combine:i.combine,mapUv:M&&m(i.map.channel),aoMapUv:ie&&m(i.aoMap.channel),lightMapUv:ae&&m(i.lightMap.channel),bumpMapUv:oe&&m(i.bumpMap.channel),normalMapUv:se&&m(i.normalMap.channel),displacementMapUv:ce&&m(i.displacementMap.channel),emissiveMapUv:le&&m(i.emissiveMap.channel),metalnessMapUv:ue&&m(i.metalnessMap.channel),roughnessMapUv:de&&m(i.roughnessMap.channel),anisotropyMapUv:ve&&m(i.anisotropyMap.channel),clearcoatMapUv:ye&&m(i.clearcoatMap.channel),clearcoatNormalMapUv:be&&m(i.clearcoatNormalMap.channel),clearcoatRoughnessMapUv:P&&m(i.clearcoatRoughnessMap.channel),iridescenceMapUv:xe&&m(i.iridescenceMap.channel),iridescenceThicknessMapUv:Se&&m(i.iridescenceThicknessMap.channel),sheenColorMapUv:Ce&&m(i.sheenColorMap.channel),sheenRoughnessMapUv:F&&m(i.sheenRoughnessMap.channel),specularMapUv:we&&m(i.specularMap.channel),specularColorMapUv:I&&m(i.specularColorMap.channel),specularIntensityMapUv:L&&m(i.specularIntensityMap.channel),transmissionMapUv:Te&&m(i.transmissionMap.channel),thicknessMapUv:Ee&&m(i.thicknessMap.channel),alphaMapUv:Oe&&m(i.alphaMap.channel),vertexTangents:!!v.attributes.tangent&&(se||fe),vertexNormals:!!v.attributes.normal,vertexColors:i.vertexColors,vertexAlphas:i.vertexColors===!0&&!!v.attributes.color&&v.attributes.color.itemSize===4,pointsUvs:h.isPoints===!0&&!!v.attributes.uv&&(M||Oe),fog:!!_,useFog:i.fog===!0,fogExp2:!!_&&_.isFogExp2,flatShading:i.wireframe===!1&&(i.flatShading===!0||v.attributes.normal===void 0&&se===!1&&(i.isMeshLambertMaterial||i.isMeshPhongMaterial||i.isMeshStandardMaterial||i.isMeshPhysicalMaterial)),sizeAttenuation:i.sizeAttenuation===!0,logarithmicDepthBuffer:d,reversedDepthBuffer:te,skinning:h.isSkinnedMesh===!0,morphTargets:v.morphAttributes.position!==void 0,morphNormals:v.morphAttributes.normal!==void 0,morphColors:v.morphAttributes.color!==void 0,morphTargetsCount:T,morphTextureStride:E,numDirLights:o.directional.length,numPointLights:o.point.length,numSpotLights:o.spot.length,numSpotLightMaps:o.spotLightMap.length,numRectAreaLights:o.rectArea.length,numHemiLights:o.hemi.length,numDirLightShadows:o.directionalShadowMap.length,numPointLightShadows:o.pointShadowMap.length,numSpotLightShadows:o.spotShadowMap.length,numSpotLightShadowsWithMaps:o.numSpotLightShadowsWithMaps,numLightProbes:o.numLightProbes,numLightProbeGrids:g.length,numClippingPlanes:a.numPlanes,numClipIntersection:a.numIntersection,dithering:i.dithering,shadowMapEnabled:e.shadowMap.enabled&&l.length>0,shadowMapType:e.shadowMap.type,toneMapping:Me,decodeVideoTexture:M&&i.map.isVideoTexture===!0&&Xo.getTransfer(i.map.colorSpace)===`srgb`,decodeVideoTextureEmissive:le&&i.emissiveMap.isVideoTexture===!0&&Xo.getTransfer(i.emissiveMap.colorSpace)===`srgb`,premultipliedAlpha:i.premultipliedAlpha,doubleSided:i.side===2,flipSided:i.side===1,useDepthPacking:i.depthPacking>=0,depthPacking:i.depthPacking||0,index0AttributeName:i.index0AttributeName,extensionClipCullDistance:je&&i.extensions.clipCullDistance===!0&&n.has(`WEBGL_clip_cull_distance`),extensionMultiDraw:(je&&i.extensions.multiDraw===!0||ne)&&n.has(`WEBGL_multi_draw`),rendererExtensionParallelShaderCompile:n.has(`KHR_parallel_shader_compile`),customProgramCacheKey:i.customProgramCacheKey()};return Ne.vertexUv1s=c.has(1),Ne.vertexUv2s=c.has(2),Ne.vertexUv3s=c.has(3),c.clear(),Ne}function g(t){let n=[];if(t.shaderID?n.push(t.shaderID):(n.push(t.customVertexShaderID),n.push(t.customFragmentShaderID)),t.defines!==void 0)for(let e in t.defines)n.push(e),n.push(t.defines[e]);return t.isRawShaderMaterial===!1&&(_(n,t),v(n,t),n.push(e.outputColorSpace)),n.push(t.customProgramCacheKey),n.join()}function _(e,t){e.push(t.precision),e.push(t.outputColorSpace),e.push(t.envMapMode),e.push(t.envMapCubeUVHeight),e.push(t.mapUv),e.push(t.alphaMapUv),e.push(t.lightMapUv),e.push(t.aoMapUv),e.push(t.bumpMapUv),e.push(t.normalMapUv),e.push(t.displacementMapUv),e.push(t.emissiveMapUv),e.push(t.metalnessMapUv),e.push(t.roughnessMapUv),e.push(t.anisotropyMapUv),e.push(t.clearcoatMapUv),e.push(t.clearcoatNormalMapUv),e.push(t.clearcoatRoughnessMapUv),e.push(t.iridescenceMapUv),e.push(t.iridescenceThicknessMapUv),e.push(t.sheenColorMapUv),e.push(t.sheenRoughnessMapUv),e.push(t.specularMapUv),e.push(t.specularColorMapUv),e.push(t.specularIntensityMapUv),e.push(t.transmissionMapUv),e.push(t.thicknessMapUv),e.push(t.combine),e.push(t.fogExp2),e.push(t.sizeAttenuation),e.push(t.morphTargetsCount),e.push(t.morphAttributeCount),e.push(t.numDirLights),e.push(t.numPointLights),e.push(t.numSpotLights),e.push(t.numSpotLightMaps),e.push(t.numHemiLights),e.push(t.numRectAreaLights),e.push(t.numDirLightShadows),e.push(t.numPointLightShadows),e.push(t.numSpotLightShadows),e.push(t.numSpotLightShadowsWithMaps),e.push(t.numLightProbes),e.push(t.shadowMapType),e.push(t.toneMapping),e.push(t.numClippingPlanes),e.push(t.numClipIntersection),e.push(t.depthPacking)}function v(e,t){o.disableAll(),t.instancing&&o.enable(0),t.instancingColor&&o.enable(1),t.instancingMorph&&o.enable(2),t.matcap&&o.enable(3),t.envMap&&o.enable(4),t.normalMapObjectSpace&&o.enable(5),t.normalMapTangentSpace&&o.enable(6),t.clearcoat&&o.enable(7),t.iridescence&&o.enable(8),t.alphaTest&&o.enable(9),t.vertexColors&&o.enable(10),t.vertexAlphas&&o.enable(11),t.vertexUv1s&&o.enable(12),t.vertexUv2s&&o.enable(13),t.vertexUv3s&&o.enable(14),t.vertexTangents&&o.enable(15),t.anisotropy&&o.enable(16),t.alphaHash&&o.enable(17),t.batching&&o.enable(18),t.dispersion&&o.enable(19),t.batchingColor&&o.enable(20),t.gradientMap&&o.enable(21),t.packedNormalMap&&o.enable(22),t.vertexNormals&&o.enable(23),e.push(o.mask),o.disableAll(),t.fog&&o.enable(0),t.useFog&&o.enable(1),t.flatShading&&o.enable(2),t.logarithmicDepthBuffer&&o.enable(3),t.reversedDepthBuffer&&o.enable(4),t.skinning&&o.enable(5),t.morphTargets&&o.enable(6),t.morphNormals&&o.enable(7),t.morphColors&&o.enable(8),t.premultipliedAlpha&&o.enable(9),t.shadowMapEnabled&&o.enable(10),t.doubleSided&&o.enable(11),t.flipSided&&o.enable(12),t.useDepthPacking&&o.enable(13),t.dithering&&o.enable(14),t.transmission&&o.enable(15),t.sheen&&o.enable(16),t.opaque&&o.enable(17),t.pointsUvs&&o.enable(18),t.decodeVideoTexture&&o.enable(19),t.decodeVideoTextureEmissive&&o.enable(20),t.alphaToCoverage&&o.enable(21),t.numLightProbeGrids>0&&o.enable(22),e.push(o.mask)}function y(e){let t=p[e.type],n;if(t){let e=jf[t];n=sd.clone(e.uniforms)}else n=e.uniforms;return n}function b(t,n){let r=u.get(n);return r===void 0?(r=new ih(e,n,t,i),l.push(r),u.set(n,r)):++r.usedTimes,r}function x(e){if(--e.usedTimes===0){let t=l.indexOf(e);l[t]=l[l.length-1],l.pop(),u.delete(e.cacheKey),e.destroy()}}function S(e){s.remove(e)}function C(){s.dispose()}return{getParameters:h,getProgramCacheKey:g,getUniforms:y,acquireProgram:b,releaseProgram:x,releaseShaderCache:S,programs:l,dispose:C}}function uh(){let e=new WeakMap;function t(t){return e.has(t)}function n(t){let n=e.get(t);return n===void 0&&(n={},e.set(t,n)),n}function r(t){e.delete(t)}function i(t,n,r){e.get(t)[n]=r}function a(){e=new WeakMap}return{has:t,get:n,remove:r,update:i,dispose:a}}function dh(e,t){return e.groupOrder===t.groupOrder?e.renderOrder===t.renderOrder?e.material.id===t.material.id?e.materialVariant===t.materialVariant?e.z===t.z?e.id-t.id:e.z-t.z:e.materialVariant-t.materialVariant:e.material.id-t.material.id:e.renderOrder-t.renderOrder:e.groupOrder-t.groupOrder}function fh(e,t){return e.groupOrder===t.groupOrder?e.renderOrder===t.renderOrder?e.z===t.z?e.id-t.id:t.z-e.z:e.renderOrder-t.renderOrder:e.groupOrder-t.groupOrder}function ph(){let e=[],t=0,n=[],r=[],i=[];function a(){t=0,n.length=0,r.length=0,i.length=0}function o(e){let t=0;return e.isInstancedMesh&&(t+=2),e.isSkinnedMesh&&(t+=1),t}function s(n,r,i,a,s,c){let l=e[t];return l===void 0?(l={id:n.id,object:n,geometry:r,material:i,materialVariant:o(n),groupOrder:a,renderOrder:n.renderOrder,z:s,group:c},e[t]=l):(l.id=n.id,l.object=n,l.geometry=r,l.material=i,l.materialVariant=o(n),l.groupOrder=a,l.renderOrder=n.renderOrder,l.z=s,l.group=c),t++,l}function c(e,t,a,o,c,l){let u=s(e,t,a,o,c,l);a.transmission>0?r.push(u):a.transparent===!0?i.push(u):n.push(u)}function l(e,t,a,o,c,l){let u=s(e,t,a,o,c,l);a.transmission>0?r.unshift(u):a.transparent===!0?i.unshift(u):n.unshift(u)}function u(e,t){n.length>1&&n.sort(e||dh),r.length>1&&r.sort(t||fh),i.length>1&&i.sort(t||fh)}function d(){for(let n=t,r=e.length;n<r;n++){let t=e[n];if(t.id===null)break;t.id=null,t.object=null,t.geometry=null,t.material=null,t.group=null}}return{opaque:n,transmissive:r,transparent:i,init:a,push:c,unshift:l,finish:d,sort:u}}function mh(){let e=new WeakMap;function t(t,n){let r=e.get(t),i;return r===void 0?(i=new ph,e.set(t,[i])):n>=r.length?(i=new ph,r.push(i)):i=r[n],i}function n(){e=new WeakMap}return{get:t,dispose:n}}function hh(){let e={};return{get:function(t){if(e[t.id]!==void 0)return e[t.id];let n;switch(t.type){case`DirectionalLight`:n={direction:new H,color:new W};break;case`SpotLight`:n={position:new H,direction:new H,color:new W,distance:0,coneCos:0,penumbraCos:0,decay:0};break;case`PointLight`:n={position:new H,color:new W,distance:0,decay:0};break;case`HemisphereLight`:n={direction:new H,skyColor:new W,groundColor:new W};break;case`RectAreaLight`:n={color:new W,position:new H,halfWidth:new H,halfHeight:new H};break}return e[t.id]=n,n}}}function gh(){let e={};return{get:function(t){if(e[t.id]!==void 0)return e[t.id];let n;switch(t.type){case`DirectionalLight`:n={shadowIntensity:1,shadowBias:0,shadowNormalBias:0,shadowRadius:1,shadowMapSize:new V};break;case`SpotLight`:n={shadowIntensity:1,shadowBias:0,shadowNormalBias:0,shadowRadius:1,shadowMapSize:new V};break;case`PointLight`:n={shadowIntensity:1,shadowBias:0,shadowNormalBias:0,shadowRadius:1,shadowMapSize:new V,shadowCameraNear:1,shadowCameraFar:1e3};break}return e[t.id]=n,n}}}var _h=0;function vh(e,t){return(t.castShadow?2:0)-(e.castShadow?2:0)+ +!!t.map-!!e.map}function yh(e){let t=new hh,n=gh(),r={version:0,hash:{directionalLength:-1,pointLength:-1,spotLength:-1,rectAreaLength:-1,hemiLength:-1,numDirectionalShadows:-1,numPointShadows:-1,numSpotShadows:-1,numSpotMaps:-1,numLightProbes:-1},ambient:[0,0,0],probe:[],directional:[],directionalShadow:[],directionalShadowMap:[],directionalShadowMatrix:[],spot:[],spotLightMap:[],spotShadow:[],spotShadowMap:[],spotLightMatrix:[],rectArea:[],rectAreaLTC1:null,rectAreaLTC2:null,point:[],pointShadow:[],pointShadowMap:[],pointShadowMatrix:[],hemi:[],numSpotLightShadowsWithMaps:0,numLightProbes:0};for(let e=0;e<9;e++)r.probe.push(new H);let i=new H,a=new fs,o=new fs;function s(i){let a=0,o=0,s=0;for(let e=0;e<9;e++)r.probe[e].set(0,0,0);let c=0,l=0,u=0,d=0,f=0,p=0,m=0,h=0,g=0,_=0,v=0;i.sort(vh);for(let e=0,y=i.length;e<y;e++){let y=i[e],b=y.color,x=y.intensity,S=y.distance,C=null;if(y.shadow&&y.shadow.map&&(C=y.shadow.map.texture.format===1030?y.shadow.map.texture:y.shadow.map.depthTexture||y.shadow.map.texture),y.isAmbientLight)a+=b.r*x,o+=b.g*x,s+=b.b*x;else if(y.isLightProbe){for(let e=0;e<9;e++)r.probe[e].addScaledVector(y.sh.coefficients[e],x);v++}else if(y.isDirectionalLight){let e=t.get(y);if(e.color.copy(y.color).multiplyScalar(y.intensity),y.castShadow){let e=y.shadow,t=n.get(y);t.shadowIntensity=e.intensity,t.shadowBias=e.bias,t.shadowNormalBias=e.normalBias,t.shadowRadius=e.radius,t.shadowMapSize=e.mapSize,r.directionalShadow[c]=t,r.directionalShadowMap[c]=C,r.directionalShadowMatrix[c]=y.shadow.matrix,p++}r.directional[c]=e,c++}else if(y.isSpotLight){let e=t.get(y);e.position.setFromMatrixPosition(y.matrixWorld),e.color.copy(b).multiplyScalar(x),e.distance=S,e.coneCos=Math.cos(y.angle),e.penumbraCos=Math.cos(y.angle*(1-y.penumbra)),e.decay=y.decay,r.spot[u]=e;let i=y.shadow;if(y.map&&(r.spotLightMap[g]=y.map,g++,i.updateMatrices(y),y.castShadow&&_++),r.spotLightMatrix[u]=i.matrix,y.castShadow){let e=n.get(y);e.shadowIntensity=i.intensity,e.shadowBias=i.bias,e.shadowNormalBias=i.normalBias,e.shadowRadius=i.radius,e.shadowMapSize=i.mapSize,r.spotShadow[u]=e,r.spotShadowMap[u]=C,h++}u++}else if(y.isRectAreaLight){let e=t.get(y);e.color.copy(b).multiplyScalar(x),e.halfWidth.set(y.width*.5,0,0),e.halfHeight.set(0,y.height*.5,0),r.rectArea[d]=e,d++}else if(y.isPointLight){let e=t.get(y);if(e.color.copy(y.color).multiplyScalar(y.intensity),e.distance=y.distance,e.decay=y.decay,y.castShadow){let e=y.shadow,t=n.get(y);t.shadowIntensity=e.intensity,t.shadowBias=e.bias,t.shadowNormalBias=e.normalBias,t.shadowRadius=e.radius,t.shadowMapSize=e.mapSize,t.shadowCameraNear=e.camera.near,t.shadowCameraFar=e.camera.far,r.pointShadow[l]=t,r.pointShadowMap[l]=C,r.pointShadowMatrix[l]=y.shadow.matrix,m++}r.point[l]=e,l++}else if(y.isHemisphereLight){let e=t.get(y);e.skyColor.copy(y.color).multiplyScalar(x),e.groundColor.copy(y.groundColor).multiplyScalar(x),r.hemi[f]=e,f++}}d>0&&(e.has(`OES_texture_float_linear`)===!0?(r.rectAreaLTC1=q.LTC_FLOAT_1,r.rectAreaLTC2=q.LTC_FLOAT_2):(r.rectAreaLTC1=q.LTC_HALF_1,r.rectAreaLTC2=q.LTC_HALF_2)),r.ambient[0]=a,r.ambient[1]=o,r.ambient[2]=s;let y=r.hash;(y.directionalLength!==c||y.pointLength!==l||y.spotLength!==u||y.rectAreaLength!==d||y.hemiLength!==f||y.numDirectionalShadows!==p||y.numPointShadows!==m||y.numSpotShadows!==h||y.numSpotMaps!==g||y.numLightProbes!==v)&&(r.directional.length=c,r.spot.length=u,r.rectArea.length=d,r.point.length=l,r.hemi.length=f,r.directionalShadow.length=p,r.directionalShadowMap.length=p,r.pointShadow.length=m,r.pointShadowMap.length=m,r.spotShadow.length=h,r.spotShadowMap.length=h,r.directionalShadowMatrix.length=p,r.pointShadowMatrix.length=m,r.spotLightMatrix.length=h+g-_,r.spotLightMap.length=g,r.numSpotLightShadowsWithMaps=_,r.numLightProbes=v,y.directionalLength=c,y.pointLength=l,y.spotLength=u,y.rectAreaLength=d,y.hemiLength=f,y.numDirectionalShadows=p,y.numPointShadows=m,y.numSpotShadows=h,y.numSpotMaps=g,y.numLightProbes=v,r.version=_h++)}function c(e,t){let n=0,s=0,c=0,l=0,u=0,d=t.matrixWorldInverse;for(let t=0,f=e.length;t<f;t++){let f=e[t];if(f.isDirectionalLight){let e=r.directional[n];e.direction.setFromMatrixPosition(f.matrixWorld),i.setFromMatrixPosition(f.target.matrixWorld),e.direction.sub(i),e.direction.transformDirection(d),n++}else if(f.isSpotLight){let e=r.spot[c];e.position.setFromMatrixPosition(f.matrixWorld),e.position.applyMatrix4(d),e.direction.setFromMatrixPosition(f.matrixWorld),i.setFromMatrixPosition(f.target.matrixWorld),e.direction.sub(i),e.direction.transformDirection(d),c++}else if(f.isRectAreaLight){let e=r.rectArea[l];e.position.setFromMatrixPosition(f.matrixWorld),e.position.applyMatrix4(d),o.identity(),a.copy(f.matrixWorld),a.premultiply(d),o.extractRotation(a),e.halfWidth.set(f.width*.5,0,0),e.halfHeight.set(0,f.height*.5,0),e.halfWidth.applyMatrix4(o),e.halfHeight.applyMatrix4(o),l++}else if(f.isPointLight){let e=r.point[s];e.position.setFromMatrixPosition(f.matrixWorld),e.position.applyMatrix4(d),s++}else if(f.isHemisphereLight){let e=r.hemi[u];e.direction.setFromMatrixPosition(f.matrixWorld),e.direction.transformDirection(d),u++}}}return{setup:s,setupView:c,state:r}}function bh(e){let t=new yh(e),n=[],r=[],i=[];function a(e){d.camera=e,n.length=0,r.length=0,i.length=0}function o(e){n.push(e)}function s(e){r.push(e)}function c(e){i.push(e)}function l(){t.setup(n)}function u(e){t.setupView(n,e)}let d={lightsArray:n,shadowsArray:r,lightProbeGridArray:i,camera:null,lights:t,transmissionRenderTarget:{},textureUnits:0};return{init:a,state:d,setupLights:l,setupLightsView:u,pushLight:o,pushShadow:s,pushLightProbeGrid:c}}function xh(e){let t=new WeakMap;function n(n,r=0){let i=t.get(n),a;return i===void 0?(a=new bh(e),t.set(n,[a])):r>=i.length?(a=new bh(e),i.push(a)):a=i[r],a}function r(){t=new WeakMap}return{get:n,dispose:r}}var Sh=`void main() {
	gl_Position = vec4( position, 1.0 );
}`,Ch=`uniform sampler2D shadow_pass;
uniform vec2 resolution;
uniform float radius;
void main() {
	const float samples = float( VSM_SAMPLES );
	float mean = 0.0;
	float squared_mean = 0.0;
	float uvStride = samples <= 1.0 ? 0.0 : 2.0 / ( samples - 1.0 );
	float uvStart = samples <= 1.0 ? 0.0 : - 1.0;
	for ( float i = 0.0; i < samples; i ++ ) {
		float uvOffset = uvStart + i * uvStride;
		#ifdef HORIZONTAL_PASS
			vec2 distribution = texture2D( shadow_pass, ( gl_FragCoord.xy + vec2( uvOffset, 0.0 ) * radius ) / resolution ).rg;
			mean += distribution.x;
			squared_mean += distribution.y * distribution.y + distribution.x * distribution.x;
		#else
			float depth = texture2D( shadow_pass, ( gl_FragCoord.xy + vec2( 0.0, uvOffset ) * radius ) / resolution ).r;
			mean += depth;
			squared_mean += depth * depth;
		#endif
	}
	mean = mean / samples;
	squared_mean = squared_mean / samples;
	float std_dev = sqrt( max( 0.0, squared_mean - mean * mean ) );
	gl_FragColor = vec4( mean, std_dev, 0.0, 1.0 );
}`,wh=[new H(1,0,0),new H(-1,0,0),new H(0,1,0),new H(0,-1,0),new H(0,0,1),new H(0,0,-1)],Th=[new H(0,-1,0),new H(0,-1,0),new H(0,0,1),new H(0,0,-1),new H(0,-1,0),new H(0,-1,0)],Eh=new fs,Dh=new H,Oh=new H;function kh(e,t,n){let r=new Yl,i=new V,a=new V,o=new ss,s=new pd,c=new md,l={},u=n.maxTextureSize,d={0:1,1:0,2:2},f=new ud({defines:{VSM_SAMPLES:8},uniforms:{shadow_pass:{value:null},resolution:{value:new V},radius:{value:4}},vertexShader:Sh,fragmentShader:Ch}),p=f.clone();p.defines.HORIZONTAL_PASS=1;let m=new Vc;m.setAttribute(`position`,new Dc(new Float32Array([-1,-1,.5,3,-1,.5,-1,3,.5]),3));let h=new kl(m,f),g=this;this.enabled=!1,this.autoUpdate=!0,this.needsUpdate=!1,this.type=1;let _=this.type;this.render=function(t,n,s){if(g.enabled===!1||g.autoUpdate===!1&&g.needsUpdate===!1||t.length===0)return;this.type===2&&(R(`WebGLShadowMap: PCFSoftShadowMap has been deprecated. Using PCFShadowMap instead.`),this.type=1);let c=e.getRenderTarget(),l=e.getActiveCubeFace(),d=e.getActiveMipmapLevel(),f=e.state;f.setBlending(0),f.buffers.depth.getReversed()===!0?f.buffers.color.setClear(0,0,0,0):f.buffers.color.setClear(1,1,1,1),f.buffers.depth.setTest(!0),f.setScissorTest(!1);let p=_!==this.type;p&&n.traverse(function(e){e.material&&(Array.isArray(e.material)?e.material.forEach(e=>e.needsUpdate=!0):e.material.needsUpdate=!0)});for(let c=0,l=t.length;c<l;c++){let l=t[c],d=l.shadow;if(d===void 0){R(`WebGLShadowMap:`,l,`has no shadow.`);continue}if(d.autoUpdate===!1&&d.needsUpdate===!1)continue;i.copy(d.mapSize);let m=d.getFrameExtents();i.multiply(m),a.copy(d.mapSize),(i.x>u||i.y>u)&&(i.x>u&&(a.x=Math.floor(u/m.x),i.x=a.x*m.x,d.mapSize.x=a.x),i.y>u&&(a.y=Math.floor(u/m.y),i.y=a.y*m.y,d.mapSize.y=a.y));let h=e.state.buffers.depth.getReversed();if(d.camera._reversedDepth=h,d.map===null||p===!0){if(d.map!==null&&(d.map.depthTexture!==null&&(d.map.depthTexture.dispose(),d.map.depthTexture=null),d.map.dispose()),this.type===3){if(l.isPointLight){R(`WebGLShadowMap: VSM shadow maps are not supported for PointLights. Use PCF or BasicShadowMap instead.`);continue}d.map=new ls(i.x,i.y,{format:ra,type:Wi,minFilter:Pi,magFilter:Pi,generateMipmaps:!1}),d.map.texture.name=l.name+`.shadowMap`,d.map.depthTexture=new du(i.x,i.y,Ui),d.map.depthTexture.name=l.name+`.shadowMapDepth`,d.map.depthTexture.format=$i,d.map.depthTexture.compareFunction=null,d.map.depthTexture.minFilter=ji,d.map.depthTexture.magFilter=ji}else l.isPointLight?(d.map=new op(i.x),d.map.depthTexture=new fu(i.x,Hi)):(d.map=new ls(i.x,i.y),d.map.depthTexture=new du(i.x,i.y,Hi)),d.map.depthTexture.name=l.name+`.shadowMap`,d.map.depthTexture.format=$i,this.type===1?(d.map.depthTexture.compareFunction=h?518:515,d.map.depthTexture.minFilter=Pi,d.map.depthTexture.magFilter=Pi):(d.map.depthTexture.compareFunction=null,d.map.depthTexture.minFilter=ji,d.map.depthTexture.magFilter=ji);d.camera.updateProjectionMatrix()}let g=d.map.isWebGLCubeRenderTarget?6:1;for(let t=0;t<g;t++){if(d.map.isWebGLCubeRenderTarget)e.setRenderTarget(d.map,t),e.clear();else{t===0&&(e.setRenderTarget(d.map),e.clear());let n=d.getViewport(t);o.set(a.x*n.x,a.y*n.y,a.x*n.z,a.y*n.w),f.viewport(o)}if(l.isPointLight){let e=d.camera,n=d.matrix,r=l.distance||e.far;r!==e.far&&(e.far=r,e.updateProjectionMatrix()),Dh.setFromMatrixPosition(l.matrixWorld),e.position.copy(Dh),Oh.copy(e.position),Oh.add(wh[t]),e.up.copy(Th[t]),e.lookAt(Oh),e.updateMatrixWorld(),n.makeTranslation(-Dh.x,-Dh.y,-Dh.z),Eh.multiplyMatrices(e.projectionMatrix,e.matrixWorldInverse),d._frustum.setFromProjectionMatrix(Eh,e.coordinateSystem,e.reversedDepth)}else d.updateMatrices(l);r=d.getFrustum(),b(n,s,d.camera,l,this.type)}d.isPointLightShadow!==!0&&this.type===3&&v(d,s),d.needsUpdate=!1}_=this.type,g.needsUpdate=!1,e.setRenderTarget(c,l,d)};function v(n,r){let a=t.update(h);f.defines.VSM_SAMPLES!==n.blurSamples&&(f.defines.VSM_SAMPLES=n.blurSamples,p.defines.VSM_SAMPLES=n.blurSamples,f.needsUpdate=!0,p.needsUpdate=!0),n.mapPass===null&&(n.mapPass=new ls(i.x,i.y,{format:ra,type:Wi})),f.uniforms.shadow_pass.value=n.map.depthTexture,f.uniforms.resolution.value=n.mapSize,f.uniforms.radius.value=n.radius,e.setRenderTarget(n.mapPass),e.clear(),e.renderBufferDirect(r,null,a,f,h,null),p.uniforms.shadow_pass.value=n.mapPass.texture,p.uniforms.resolution.value=n.mapSize,p.uniforms.radius.value=n.radius,e.setRenderTarget(n.map),e.clear(),e.renderBufferDirect(r,null,a,p,h,null)}function y(t,n,r,i){let a=null,o=r.isPointLight===!0?t.customDistanceMaterial:t.customDepthMaterial;if(o!==void 0)a=o;else if(a=r.isPointLight===!0?c:s,e.localClippingEnabled&&n.clipShadows===!0&&Array.isArray(n.clippingPlanes)&&n.clippingPlanes.length!==0||n.displacementMap&&n.displacementScale!==0||n.alphaMap&&n.alphaTest>0||n.map&&n.alphaTest>0||n.alphaToCoverage===!0){let e=a.uuid,t=n.uuid,r=l[e];r===void 0&&(r={},l[e]=r);let i=r[t];i===void 0&&(i=a.clone(),r[t]=i,n.addEventListener(`dispose`,x)),a=i}if(a.visible=n.visible,a.wireframe=n.wireframe,i===3?a.side=n.shadowSide===null?n.side:n.shadowSide:a.side=n.shadowSide===null?d[n.side]:n.shadowSide,a.alphaMap=n.alphaMap,a.alphaTest=n.alphaToCoverage===!0?.5:n.alphaTest,a.map=n.map,a.clipShadows=n.clipShadows,a.clippingPlanes=n.clippingPlanes,a.clipIntersection=n.clipIntersection,a.displacementMap=n.displacementMap,a.displacementScale=n.displacementScale,a.displacementBias=n.displacementBias,a.wireframeLinewidth=n.wireframeLinewidth,a.linewidth=n.linewidth,r.isPointLight===!0&&a.isMeshDistanceMaterial===!0){let t=e.properties.get(a);t.light=r}return a}function b(n,i,a,o,s){if(n.visible===!1)return;if(n.layers.test(i.layers)&&(n.isMesh||n.isLine||n.isPoints)&&(n.castShadow||n.receiveShadow&&s===3)&&(!n.frustumCulled||r.intersectsObject(n))){n.modelViewMatrix.multiplyMatrices(a.matrixWorldInverse,n.matrixWorld);let r=t.update(n),c=n.material;if(Array.isArray(c)){let t=r.groups;for(let l=0,u=t.length;l<u;l++){let u=t[l],d=c[u.materialIndex];if(d&&d.visible){let t=y(n,d,o,s);n.onBeforeShadow(e,n,i,a,r,t,u),e.renderBufferDirect(a,null,r,t,n,u),n.onAfterShadow(e,n,i,a,r,t,u)}}}else if(c.visible){let t=y(n,c,o,s);n.onBeforeShadow(e,n,i,a,r,t,null),e.renderBufferDirect(a,null,r,t,n,null),n.onAfterShadow(e,n,i,a,r,t,null)}}let c=n.children;for(let e=0,t=c.length;e<t;e++)b(c[e],i,a,o,s)}function x(e){e.target.removeEventListener(`dispose`,x);for(let t in l){let n=l[t],r=e.target.uuid;r in n&&(n[r].dispose(),delete n[r])}}}function Ah(e,t){function n(){let t=!1,n=new ss,r=null,i=new ss(0,0,0,0);return{setMask:function(n){r!==n&&!t&&(e.colorMask(n,n,n,n),r=n)},setLocked:function(e){t=e},setClear:function(t,r,a,o,s){s===!0&&(t*=o,r*=o,a*=o),n.set(t,r,a,o),i.equals(n)===!1&&(e.clearColor(t,r,a,o),i.copy(n))},reset:function(){t=!1,r=null,i.set(-1,0,0,0)}}}function r(){let n=!1,r=!1,i=null,a=null,o=null;return{setReversed:function(e){if(r!==e){let n=t.get(`EXT_clip_control`);e?n.clipControlEXT(n.LOWER_LEFT_EXT,n.ZERO_TO_ONE_EXT):n.clipControlEXT(n.LOWER_LEFT_EXT,n.NEGATIVE_ONE_TO_ONE_EXT),r=e;let i=o;o=null,this.setClear(i)}},getReversed:function(){return r},setTest:function(t){t?ue(e.DEPTH_TEST):de(e.DEPTH_TEST)},setMask:function(t){i!==t&&!n&&(e.depthMask(t),i=t)},setFunc:function(t){if(r&&(t=ho[t]),a!==t){switch(t){case 0:e.depthFunc(e.NEVER);break;case 1:e.depthFunc(e.ALWAYS);break;case 2:e.depthFunc(e.LESS);break;case 3:e.depthFunc(e.LEQUAL);break;case 4:e.depthFunc(e.EQUAL);break;case 5:e.depthFunc(e.GEQUAL);break;case 6:e.depthFunc(e.GREATER);break;case 7:e.depthFunc(e.NOTEQUAL);break;default:e.depthFunc(e.LEQUAL)}a=t}},setLocked:function(e){n=e},setClear:function(t){o!==t&&(o=t,r&&(t=1-t),e.clearDepth(t))},reset:function(){n=!1,i=null,a=null,o=null,r=!1}}}function i(){let t=!1,n=null,r=null,i=null,a=null,o=null,s=null,c=null,l=null;return{setTest:function(n){t||(n?ue(e.STENCIL_TEST):de(e.STENCIL_TEST))},setMask:function(r){n!==r&&!t&&(e.stencilMask(r),n=r)},setFunc:function(t,n,o){(r!==t||i!==n||a!==o)&&(e.stencilFunc(t,n,o),r=t,i=n,a=o)},setOp:function(t,n,r){(o!==t||s!==n||c!==r)&&(e.stencilOp(t,n,r),o=t,s=n,c=r)},setLocked:function(e){t=e},setClear:function(t){l!==t&&(e.clearStencil(t),l=t)},reset:function(){t=!1,n=null,r=null,i=null,a=null,o=null,s=null,c=null,l=null}}}let a=new n,o=new r,s=new i,c=new WeakMap,l=new WeakMap,u={},d={},f={},p=new WeakMap,m=[],h=null,g=!1,_=null,v=null,y=null,b=null,x=null,S=null,C=null,w=new W(0,0,0),T=0,E=!1,D=null,O=null,k=null,A=null,ee=null,te=e.getParameter(e.MAX_COMBINED_TEXTURE_IMAGE_UNITS),j=!1,ne=0,M=e.getParameter(e.VERSION);M.indexOf(`WebGL`)===-1?M.indexOf(`OpenGL ES`)!==-1&&(ne=parseFloat(/^OpenGL ES (\d)/.exec(M)[1]),j=ne>=2):(ne=parseFloat(/^WebGL (\d)/.exec(M)[1]),j=ne>=1);let re=null,N={},ie=e.getParameter(e.SCISSOR_BOX),ae=e.getParameter(e.VIEWPORT),oe=new ss().fromArray(ie),se=new ss().fromArray(ae);function ce(t,n,r,i){let a=new Uint8Array(4),o=e.createTexture();e.bindTexture(t,o),e.texParameteri(t,e.TEXTURE_MIN_FILTER,e.NEAREST),e.texParameteri(t,e.TEXTURE_MAG_FILTER,e.NEAREST);for(let o=0;o<r;o++)t===e.TEXTURE_3D||t===e.TEXTURE_2D_ARRAY?e.texImage3D(n,0,e.RGBA,1,1,i,0,e.RGBA,e.UNSIGNED_BYTE,a):e.texImage2D(n+o,0,e.RGBA,1,1,0,e.RGBA,e.UNSIGNED_BYTE,a);return o}let le={};le[e.TEXTURE_2D]=ce(e.TEXTURE_2D,e.TEXTURE_2D,1),le[e.TEXTURE_CUBE_MAP]=ce(e.TEXTURE_CUBE_MAP,e.TEXTURE_CUBE_MAP_POSITIVE_X,6),le[e.TEXTURE_2D_ARRAY]=ce(e.TEXTURE_2D_ARRAY,e.TEXTURE_2D_ARRAY,1,1),le[e.TEXTURE_3D]=ce(e.TEXTURE_3D,e.TEXTURE_3D,1,1),a.setClear(0,0,0,1),o.setClear(1),s.setClear(0),ue(e.DEPTH_TEST),o.setFunc(3),ye(!1),be(1),ue(e.CULL_FACE),_e(0);function ue(t){u[t]!==!0&&(e.enable(t),u[t]=!0)}function de(t){u[t]!==!1&&(e.disable(t),u[t]=!1)}function fe(t,n){return f[t]===n?!1:(e.bindFramebuffer(t,n),f[t]=n,t===e.DRAW_FRAMEBUFFER&&(f[e.FRAMEBUFFER]=n),t===e.FRAMEBUFFER&&(f[e.DRAW_FRAMEBUFFER]=n),!0)}function pe(t,n){let r=m,i=!1;if(t){r=p.get(n),r===void 0&&(r=[],p.set(n,r));let a=t.textures;if(r.length!==a.length||r[0]!==e.COLOR_ATTACHMENT0){for(let t=0,n=a.length;t<n;t++)r[t]=e.COLOR_ATTACHMENT0+t;r.length=a.length,i=!0}}else r[0]!==e.BACK&&(r[0]=e.BACK,i=!0);i&&e.drawBuffers(r)}function me(t){return h===t?!1:(e.useProgram(t),h=t,!0)}let he={100:e.FUNC_ADD,101:e.FUNC_SUBTRACT,102:e.FUNC_REVERSE_SUBTRACT};he[103]=e.MIN,he[104]=e.MAX;let ge={200:e.ZERO,201:e.ONE,202:e.SRC_COLOR,204:e.SRC_ALPHA,210:e.SRC_ALPHA_SATURATE,208:e.DST_COLOR,206:e.DST_ALPHA,203:e.ONE_MINUS_SRC_COLOR,205:e.ONE_MINUS_SRC_ALPHA,209:e.ONE_MINUS_DST_COLOR,207:e.ONE_MINUS_DST_ALPHA,211:e.CONSTANT_COLOR,212:e.ONE_MINUS_CONSTANT_COLOR,213:e.CONSTANT_ALPHA,214:e.ONE_MINUS_CONSTANT_ALPHA};function _e(t,n,r,i,a,o,s,c,l,u){if(t===0){g===!0&&(de(e.BLEND),g=!1);return}if(g===!1&&(ue(e.BLEND),g=!0),t!==5){if(t!==_||u!==E){if((v!==100||x!==100)&&(e.blendEquation(e.FUNC_ADD),v=100,x=100),u)switch(t){case 1:e.blendFuncSeparate(e.ONE,e.ONE_MINUS_SRC_ALPHA,e.ONE,e.ONE_MINUS_SRC_ALPHA);break;case 2:e.blendFunc(e.ONE,e.ONE);break;case 3:e.blendFuncSeparate(e.ZERO,e.ONE_MINUS_SRC_COLOR,e.ZERO,e.ONE);break;case 4:e.blendFuncSeparate(e.DST_COLOR,e.ONE_MINUS_SRC_ALPHA,e.ZERO,e.ONE);break;default:z(`WebGLState: Invalid blending: `,t);break}else switch(t){case 1:e.blendFuncSeparate(e.SRC_ALPHA,e.ONE_MINUS_SRC_ALPHA,e.ONE,e.ONE_MINUS_SRC_ALPHA);break;case 2:e.blendFuncSeparate(e.SRC_ALPHA,e.ONE,e.ONE,e.ONE);break;case 3:z(`WebGLState: SubtractiveBlending requires material.premultipliedAlpha = true`);break;case 4:z(`WebGLState: MultiplyBlending requires material.premultipliedAlpha = true`);break;default:z(`WebGLState: Invalid blending: `,t);break}y=null,b=null,S=null,C=null,w.set(0,0,0),T=0,_=t,E=u}return}a||=n,o||=r,s||=i,(n!==v||a!==x)&&(e.blendEquationSeparate(he[n],he[a]),v=n,x=a),(r!==y||i!==b||o!==S||s!==C)&&(e.blendFuncSeparate(ge[r],ge[i],ge[o],ge[s]),y=r,b=i,S=o,C=s),(c.equals(w)===!1||l!==T)&&(e.blendColor(c.r,c.g,c.b,l),w.copy(c),T=l),_=t,E=!1}function ve(t,n){t.side===2?de(e.CULL_FACE):ue(e.CULL_FACE);let r=t.side===1;n&&(r=!r),ye(r),t.blending===1&&t.transparent===!1?_e(0):_e(t.blending,t.blendEquation,t.blendSrc,t.blendDst,t.blendEquationAlpha,t.blendSrcAlpha,t.blendDstAlpha,t.blendColor,t.blendAlpha,t.premultipliedAlpha),o.setFunc(t.depthFunc),o.setTest(t.depthTest),o.setMask(t.depthWrite),a.setMask(t.colorWrite);let i=t.stencilWrite;s.setTest(i),i&&(s.setMask(t.stencilWriteMask),s.setFunc(t.stencilFunc,t.stencilRef,t.stencilFuncMask),s.setOp(t.stencilFail,t.stencilZFail,t.stencilZPass)),xe(t.polygonOffset,t.polygonOffsetFactor,t.polygonOffsetUnits),t.alphaToCoverage===!0?ue(e.SAMPLE_ALPHA_TO_COVERAGE):de(e.SAMPLE_ALPHA_TO_COVERAGE)}function ye(t){D!==t&&(t?e.frontFace(e.CW):e.frontFace(e.CCW),D=t)}function be(t){t===0?de(e.CULL_FACE):(ue(e.CULL_FACE),t!==O&&(t===1?e.cullFace(e.BACK):t===2?e.cullFace(e.FRONT):e.cullFace(e.FRONT_AND_BACK))),O=t}function P(t){t!==k&&(j&&e.lineWidth(t),k=t)}function xe(t,n,r){t?(ue(e.POLYGON_OFFSET_FILL),(A!==n||ee!==r)&&(A=n,ee=r,o.getReversed()&&(n=-n),e.polygonOffset(n,r))):de(e.POLYGON_OFFSET_FILL)}function Se(t){t?ue(e.SCISSOR_TEST):de(e.SCISSOR_TEST)}function Ce(t){t===void 0&&(t=e.TEXTURE0+te-1),re!==t&&(e.activeTexture(t),re=t)}function F(t,n,r){r===void 0&&(r=re===null?e.TEXTURE0+te-1:re);let i=N[r];i===void 0&&(i={type:void 0,texture:void 0},N[r]=i),(i.type!==t||i.texture!==n)&&(re!==r&&(e.activeTexture(r),re=r),e.bindTexture(t,n||le[t]),i.type=t,i.texture=n)}function we(){let t=N[re];t!==void 0&&t.type!==void 0&&(e.bindTexture(t.type,null),t.type=void 0,t.texture=void 0)}function I(){try{e.compressedTexImage2D(...arguments)}catch(e){z(`WebGLState:`,e)}}function L(){try{e.compressedTexImage3D(...arguments)}catch(e){z(`WebGLState:`,e)}}function Te(){try{e.texSubImage2D(...arguments)}catch(e){z(`WebGLState:`,e)}}function Ee(){try{e.texSubImage3D(...arguments)}catch(e){z(`WebGLState:`,e)}}function De(){try{e.compressedTexSubImage2D(...arguments)}catch(e){z(`WebGLState:`,e)}}function Oe(){try{e.compressedTexSubImage3D(...arguments)}catch(e){z(`WebGLState:`,e)}}function ke(){try{e.texStorage2D(...arguments)}catch(e){z(`WebGLState:`,e)}}function Ae(){try{e.texStorage3D(...arguments)}catch(e){z(`WebGLState:`,e)}}function je(){try{e.texImage2D(...arguments)}catch(e){z(`WebGLState:`,e)}}function Me(){try{e.texImage3D(...arguments)}catch(e){z(`WebGLState:`,e)}}function Ne(t){return d[t]===void 0?e.getParameter(t):d[t]}function Pe(t,n){d[t]!==n&&(e.pixelStorei(t,n),d[t]=n)}function Fe(t){oe.equals(t)===!1&&(e.scissor(t.x,t.y,t.z,t.w),oe.copy(t))}function Ie(t){se.equals(t)===!1&&(e.viewport(t.x,t.y,t.z,t.w),se.copy(t))}function Le(t,n){let r=l.get(n);r===void 0&&(r=new WeakMap,l.set(n,r));let i=r.get(t);i===void 0&&(i=e.getUniformBlockIndex(n,t.name),r.set(t,i))}function Re(t,n){let r=l.get(n).get(t);c.get(n)!==r&&(e.uniformBlockBinding(n,r,t.__bindingPointIndex),c.set(n,r))}function ze(){e.disable(e.BLEND),e.disable(e.CULL_FACE),e.disable(e.DEPTH_TEST),e.disable(e.POLYGON_OFFSET_FILL),e.disable(e.SCISSOR_TEST),e.disable(e.STENCIL_TEST),e.disable(e.SAMPLE_ALPHA_TO_COVERAGE),e.blendEquation(e.FUNC_ADD),e.blendFunc(e.ONE,e.ZERO),e.blendFuncSeparate(e.ONE,e.ZERO,e.ONE,e.ZERO),e.blendColor(0,0,0,0),e.colorMask(!0,!0,!0,!0),e.clearColor(0,0,0,0),e.depthMask(!0),e.depthFunc(e.LESS),o.setReversed(!1),e.clearDepth(1),e.stencilMask(4294967295),e.stencilFunc(e.ALWAYS,0,4294967295),e.stencilOp(e.KEEP,e.KEEP,e.KEEP),e.clearStencil(0),e.cullFace(e.BACK),e.frontFace(e.CCW),e.polygonOffset(0,0),e.activeTexture(e.TEXTURE0),e.bindFramebuffer(e.FRAMEBUFFER,null),e.bindFramebuffer(e.DRAW_FRAMEBUFFER,null),e.bindFramebuffer(e.READ_FRAMEBUFFER,null),e.useProgram(null),e.lineWidth(1),e.scissor(0,0,e.canvas.width,e.canvas.height),e.viewport(0,0,e.canvas.width,e.canvas.height),e.pixelStorei(e.PACK_ALIGNMENT,4),e.pixelStorei(e.UNPACK_ALIGNMENT,4),e.pixelStorei(e.UNPACK_FLIP_Y_WEBGL,!1),e.pixelStorei(e.UNPACK_PREMULTIPLY_ALPHA_WEBGL,!1),e.pixelStorei(e.UNPACK_COLORSPACE_CONVERSION_WEBGL,e.BROWSER_DEFAULT_WEBGL),e.pixelStorei(e.PACK_ROW_LENGTH,0),e.pixelStorei(e.PACK_SKIP_PIXELS,0),e.pixelStorei(e.PACK_SKIP_ROWS,0),e.pixelStorei(e.UNPACK_ROW_LENGTH,0),e.pixelStorei(e.UNPACK_IMAGE_HEIGHT,0),e.pixelStorei(e.UNPACK_SKIP_PIXELS,0),e.pixelStorei(e.UNPACK_SKIP_ROWS,0),e.pixelStorei(e.UNPACK_SKIP_IMAGES,0),u={},d={},re=null,N={},f={},p=new WeakMap,m=[],h=null,g=!1,_=null,v=null,y=null,b=null,x=null,S=null,C=null,w=new W(0,0,0),T=0,E=!1,D=null,O=null,k=null,A=null,ee=null,oe.set(0,0,e.canvas.width,e.canvas.height),se.set(0,0,e.canvas.width,e.canvas.height),a.reset(),o.reset(),s.reset()}return{buffers:{color:a,depth:o,stencil:s},enable:ue,disable:de,bindFramebuffer:fe,drawBuffers:pe,useProgram:me,setBlending:_e,setMaterial:ve,setFlipSided:ye,setCullFace:be,setLineWidth:P,setPolygonOffset:xe,setScissorTest:Se,activeTexture:Ce,bindTexture:F,unbindTexture:we,compressedTexImage2D:I,compressedTexImage3D:L,texImage2D:je,texImage3D:Me,pixelStorei:Pe,getParameter:Ne,updateUBOMapping:Le,uniformBlockBinding:Re,texStorage2D:ke,texStorage3D:Ae,texSubImage2D:Te,texSubImage3D:Ee,compressedTexSubImage2D:De,compressedTexSubImage3D:Oe,scissor:Fe,viewport:Ie,reset:ze}}function jh(e,t,n,r,i,a,o){let s=t.has(`WEBGL_multisampled_render_to_texture`)?t.get(`WEBGL_multisampled_render_to_texture`):null,c=typeof navigator>`u`?!1:/OculusBrowser/g.test(navigator.userAgent),l=new V,u=new WeakMap,d=new Set,f,p=new WeakMap,m=!1;try{m=typeof OffscreenCanvas<`u`&&new OffscreenCanvas(1,1).getContext(`2d`)!==null}catch{}function h(e,t){return m?new OffscreenCanvas(e,t):oo(`canvas`)}function g(e,t,n){let r=1,i=I(e);if((i.width>n||i.height>n)&&(r=n/Math.max(i.width,i.height)),r<1)if(typeof HTMLImageElement<`u`&&e instanceof HTMLImageElement||typeof HTMLCanvasElement<`u`&&e instanceof HTMLCanvasElement||typeof ImageBitmap<`u`&&e instanceof ImageBitmap||typeof VideoFrame<`u`&&e instanceof VideoFrame){let n=Math.floor(r*i.width),a=Math.floor(r*i.height);f===void 0&&(f=h(n,a));let o=t?h(n,a):f;return o.width=n,o.height=a,o.getContext(`2d`).drawImage(e,0,0,n,a),R(`WebGLRenderer: Texture has been resized from (`+i.width+`x`+i.height+`) to (`+n+`x`+a+`).`),o}else return`data`in e&&R(`WebGLRenderer: Image in DataTexture is too big (`+i.width+`x`+i.height+`).`),e;return e}function _(e){return e.generateMipmaps}function v(t){e.generateMipmap(t)}function y(t){return t.isWebGLCubeRenderTarget?e.TEXTURE_CUBE_MAP:t.isWebGL3DRenderTarget?e.TEXTURE_3D:t.isWebGLArrayRenderTarget||t.isCompressedArrayTexture?e.TEXTURE_2D_ARRAY:e.TEXTURE_2D}function b(n,r,i,a,o,s=!1){if(n!==null){if(e[n]!==void 0)return e[n];R(`WebGLRenderer: Attempt to use non-existing WebGL internal format '`+n+`'`)}let c;a&&(c=t.get(`EXT_texture_norm16`),c||R(`WebGLRenderer: Unable to use normalized textures without EXT_texture_norm16 extension`));let l=r;if(r===e.RED&&(i===e.FLOAT&&(l=e.R32F),i===e.HALF_FLOAT&&(l=e.R16F),i===e.UNSIGNED_BYTE&&(l=e.R8),i===e.UNSIGNED_SHORT&&c&&(l=c.R16_EXT),i===e.SHORT&&c&&(l=c.R16_SNORM_EXT)),r===e.RED_INTEGER&&(i===e.UNSIGNED_BYTE&&(l=e.R8UI),i===e.UNSIGNED_SHORT&&(l=e.R16UI),i===e.UNSIGNED_INT&&(l=e.R32UI),i===e.BYTE&&(l=e.R8I),i===e.SHORT&&(l=e.R16I),i===e.INT&&(l=e.R32I)),r===e.RG&&(i===e.FLOAT&&(l=e.RG32F),i===e.HALF_FLOAT&&(l=e.RG16F),i===e.UNSIGNED_BYTE&&(l=e.RG8),i===e.UNSIGNED_SHORT&&c&&(l=c.RG16_EXT),i===e.SHORT&&c&&(l=c.RG16_SNORM_EXT)),r===e.RG_INTEGER&&(i===e.UNSIGNED_BYTE&&(l=e.RG8UI),i===e.UNSIGNED_SHORT&&(l=e.RG16UI),i===e.UNSIGNED_INT&&(l=e.RG32UI),i===e.BYTE&&(l=e.RG8I),i===e.SHORT&&(l=e.RG16I),i===e.INT&&(l=e.RG32I)),r===e.RGB_INTEGER&&(i===e.UNSIGNED_BYTE&&(l=e.RGB8UI),i===e.UNSIGNED_SHORT&&(l=e.RGB16UI),i===e.UNSIGNED_INT&&(l=e.RGB32UI),i===e.BYTE&&(l=e.RGB8I),i===e.SHORT&&(l=e.RGB16I),i===e.INT&&(l=e.RGB32I)),r===e.RGBA_INTEGER&&(i===e.UNSIGNED_BYTE&&(l=e.RGBA8UI),i===e.UNSIGNED_SHORT&&(l=e.RGBA16UI),i===e.UNSIGNED_INT&&(l=e.RGBA32UI),i===e.BYTE&&(l=e.RGBA8I),i===e.SHORT&&(l=e.RGBA16I),i===e.INT&&(l=e.RGBA32I)),r===e.RGB&&(i===e.UNSIGNED_SHORT&&c&&(l=c.RGB16_EXT),i===e.SHORT&&c&&(l=c.RGB16_SNORM_EXT),i===e.UNSIGNED_INT_5_9_9_9_REV&&(l=e.RGB9_E5),i===e.UNSIGNED_INT_10F_11F_11F_REV&&(l=e.R11F_G11F_B10F)),r===e.RGBA){let t=s?$a:Xo.getTransfer(o);i===e.FLOAT&&(l=e.RGBA32F),i===e.HALF_FLOAT&&(l=e.RGBA16F),i===e.UNSIGNED_BYTE&&(l=t===`srgb`?e.SRGB8_ALPHA8:e.RGBA8),i===e.UNSIGNED_SHORT&&c&&(l=c.RGBA16_EXT),i===e.SHORT&&c&&(l=c.RGBA16_SNORM_EXT),i===e.UNSIGNED_SHORT_4_4_4_4&&(l=e.RGBA4),i===e.UNSIGNED_SHORT_5_5_5_1&&(l=e.RGB5_A1)}return(l===e.R16F||l===e.R32F||l===e.RG16F||l===e.RG32F||l===e.RGBA16F||l===e.RGBA32F)&&t.get(`EXT_color_buffer_float`),l}function x(t,n){let r;return t?n===null||n===1014||n===1020?r=e.DEPTH24_STENCIL8:n===1015?r=e.DEPTH32F_STENCIL8:n===1012&&(r=e.DEPTH24_STENCIL8,R(`DepthTexture: 16 bit depth attachment is not supported with stencil. Using 24-bit attachment.`)):n===null||n===1014||n===1020?r=e.DEPTH_COMPONENT24:n===1015?r=e.DEPTH_COMPONENT32F:n===1012&&(r=e.DEPTH_COMPONENT16),r}function S(e,t){return _(e)===!0||e.isFramebufferTexture&&e.minFilter!==1003&&e.minFilter!==1006?Math.log2(Math.max(t.width,t.height))+1:e.mipmaps!==void 0&&e.mipmaps.length>0?e.mipmaps.length:e.isCompressedTexture&&Array.isArray(e.image)?t.mipmaps.length:1}function C(e){let t=e.target;t.removeEventListener(`dispose`,C),T(t),t.isVideoTexture&&u.delete(t),t.isHTMLTexture&&d.delete(t)}function w(e){let t=e.target;t.removeEventListener(`dispose`,w),D(t)}function T(e){let t=r.get(e);if(t.__webglInit===void 0)return;let n=e.source,i=p.get(n);if(i){let r=i[t.__cacheKey];r.usedTimes--,r.usedTimes===0&&E(e),Object.keys(i).length===0&&p.delete(n)}r.remove(e)}function E(t){let n=r.get(t);e.deleteTexture(n.__webglTexture);let i=t.source,a=p.get(i);delete a[n.__cacheKey],o.memory.textures--}function D(t){let n=r.get(t);if(t.depthTexture&&(t.depthTexture.dispose(),r.remove(t.depthTexture)),t.isWebGLCubeRenderTarget)for(let t=0;t<6;t++){if(Array.isArray(n.__webglFramebuffer[t]))for(let r=0;r<n.__webglFramebuffer[t].length;r++)e.deleteFramebuffer(n.__webglFramebuffer[t][r]);else e.deleteFramebuffer(n.__webglFramebuffer[t]);n.__webglDepthbuffer&&e.deleteRenderbuffer(n.__webglDepthbuffer[t])}else{if(Array.isArray(n.__webglFramebuffer))for(let t=0;t<n.__webglFramebuffer.length;t++)e.deleteFramebuffer(n.__webglFramebuffer[t]);else e.deleteFramebuffer(n.__webglFramebuffer);if(n.__webglDepthbuffer&&e.deleteRenderbuffer(n.__webglDepthbuffer),n.__webglMultisampledFramebuffer&&e.deleteFramebuffer(n.__webglMultisampledFramebuffer),n.__webglColorRenderbuffer)for(let t=0;t<n.__webglColorRenderbuffer.length;t++)n.__webglColorRenderbuffer[t]&&e.deleteRenderbuffer(n.__webglColorRenderbuffer[t]);n.__webglDepthRenderbuffer&&e.deleteRenderbuffer(n.__webglDepthRenderbuffer)}let i=t.textures;for(let t=0,n=i.length;t<n;t++){let n=r.get(i[t]);n.__webglTexture&&(e.deleteTexture(n.__webglTexture),o.memory.textures--),r.remove(i[t])}r.remove(t)}let O=0;function k(){O=0}function A(){return O}function ee(e){O=e}function te(){let e=O;return e>=i.maxTextures&&R(`WebGLTextures: Trying to use `+e+` texture units while this GPU supports only `+i.maxTextures),O+=1,e}function j(e){let t=[];return t.push(e.wrapS),t.push(e.wrapT),t.push(e.wrapR||0),t.push(e.magFilter),t.push(e.minFilter),t.push(e.anisotropy),t.push(e.internalFormat),t.push(e.format),t.push(e.type),t.push(e.generateMipmaps),t.push(e.premultiplyAlpha),t.push(e.flipY),t.push(e.unpackAlignment),t.push(e.colorSpace),t.join()}function ne(t,i){let a=r.get(t);if(t.isVideoTexture&&F(t),t.isRenderTargetTexture===!1&&t.isExternalTexture!==!0&&t.version>0&&a.__version!==t.version){let e=t.image;if(e===null)R(`WebGLRenderer: Texture marked for update but no image data found.`);else if(e.complete===!1)R(`WebGLRenderer: Texture marked for update but image is incomplete`);else{de(a,t,i);return}}else t.isExternalTexture&&(a.__webglTexture=t.sourceTexture?t.sourceTexture:null);n.bindTexture(e.TEXTURE_2D,a.__webglTexture,e.TEXTURE0+i)}function M(t,i){let a=r.get(t);if(t.isRenderTargetTexture===!1&&t.version>0&&a.__version!==t.version){de(a,t,i);return}else t.isExternalTexture&&(a.__webglTexture=t.sourceTexture?t.sourceTexture:null);n.bindTexture(e.TEXTURE_2D_ARRAY,a.__webglTexture,e.TEXTURE0+i)}function re(t,i){let a=r.get(t);if(t.isRenderTargetTexture===!1&&t.version>0&&a.__version!==t.version){de(a,t,i);return}n.bindTexture(e.TEXTURE_3D,a.__webglTexture,e.TEXTURE0+i)}function N(t,i){let a=r.get(t);if(t.isCubeDepthTexture!==!0&&t.version>0&&a.__version!==t.version){fe(a,t,i);return}n.bindTexture(e.TEXTURE_CUBE_MAP,a.__webglTexture,e.TEXTURE0+i)}let ie={[Oi]:e.REPEAT,[ki]:e.CLAMP_TO_EDGE,[Ai]:e.MIRRORED_REPEAT},ae={[ji]:e.NEAREST,[Mi]:e.NEAREST_MIPMAP_NEAREST,[Ni]:e.NEAREST_MIPMAP_LINEAR,[Pi]:e.LINEAR,[Fi]:e.LINEAR_MIPMAP_NEAREST,[Ii]:e.LINEAR_MIPMAP_LINEAR},oe={512:e.NEVER,519:e.ALWAYS,513:e.LESS,515:e.LEQUAL,514:e.EQUAL,518:e.GEQUAL,516:e.GREATER,517:e.NOTEQUAL};function se(n,a){if(a.type===1015&&t.has(`OES_texture_float_linear`)===!1&&(a.magFilter===1006||a.magFilter===1007||a.magFilter===1005||a.magFilter===1008||a.minFilter===1006||a.minFilter===1007||a.minFilter===1005||a.minFilter===1008)&&R(`WebGLRenderer: Unable to use linear filtering with floating point textures. OES_texture_float_linear not supported on this device.`),e.texParameteri(n,e.TEXTURE_WRAP_S,ie[a.wrapS]),e.texParameteri(n,e.TEXTURE_WRAP_T,ie[a.wrapT]),(n===e.TEXTURE_3D||n===e.TEXTURE_2D_ARRAY)&&e.texParameteri(n,e.TEXTURE_WRAP_R,ie[a.wrapR]),e.texParameteri(n,e.TEXTURE_MAG_FILTER,ae[a.magFilter]),e.texParameteri(n,e.TEXTURE_MIN_FILTER,ae[a.minFilter]),a.compareFunction&&(e.texParameteri(n,e.TEXTURE_COMPARE_MODE,e.COMPARE_REF_TO_TEXTURE),e.texParameteri(n,e.TEXTURE_COMPARE_FUNC,oe[a.compareFunction])),t.has(`EXT_texture_filter_anisotropic`)===!0){if(a.magFilter===1003||a.minFilter!==1005&&a.minFilter!==1008||a.type===1015&&t.has(`OES_texture_float_linear`)===!1)return;if(a.anisotropy>1||r.get(a).__currentAnisotropy){let o=t.get(`EXT_texture_filter_anisotropic`);e.texParameterf(n,o.TEXTURE_MAX_ANISOTROPY_EXT,Math.min(a.anisotropy,i.getMaxAnisotropy())),r.get(a).__currentAnisotropy=a.anisotropy}}}function ce(t,n){let r=!1;t.__webglInit===void 0&&(t.__webglInit=!0,n.addEventListener(`dispose`,C));let i=n.source,a=p.get(i);a===void 0&&(a={},p.set(i,a));let s=j(n);if(s!==t.__cacheKey){a[s]===void 0&&(a[s]={texture:e.createTexture(),usedTimes:0},o.memory.textures++,r=!0),a[s].usedTimes++;let i=a[t.__cacheKey];i!==void 0&&(a[t.__cacheKey].usedTimes--,i.usedTimes===0&&E(n)),t.__cacheKey=s,t.__webglTexture=a[s].texture}return r}function le(e,t,n){return Math.floor(Math.floor(e/n)/t)}function ue(t,r,i,a){let o=t.updateRanges;if(o.length===0)n.texSubImage2D(e.TEXTURE_2D,0,0,0,r.width,r.height,i,a,r.data);else{o.sort((e,t)=>e.start-t.start);let s=0;for(let e=1;e<o.length;e++){let t=o[s],n=o[e],i=t.start+t.count,a=le(n.start,r.width,4),c=le(t.start,r.width,4);n.start<=i+1&&a===c&&le(n.start+n.count-1,r.width,4)===a?t.count=Math.max(t.count,n.start+n.count-t.start):(++s,o[s]=n)}o.length=s+1;let c=n.getParameter(e.UNPACK_ROW_LENGTH),l=n.getParameter(e.UNPACK_SKIP_PIXELS),u=n.getParameter(e.UNPACK_SKIP_ROWS);n.pixelStorei(e.UNPACK_ROW_LENGTH,r.width);for(let t=0,s=o.length;t<s;t++){let s=o[t],c=Math.floor(s.start/4),l=Math.ceil(s.count/4),u=c%r.width,d=Math.floor(c/r.width),f=l;n.pixelStorei(e.UNPACK_SKIP_PIXELS,u),n.pixelStorei(e.UNPACK_SKIP_ROWS,d),n.texSubImage2D(e.TEXTURE_2D,0,u,d,f,1,i,a,r.data)}t.clearUpdateRanges(),n.pixelStorei(e.UNPACK_ROW_LENGTH,c),n.pixelStorei(e.UNPACK_SKIP_PIXELS,l),n.pixelStorei(e.UNPACK_SKIP_ROWS,u)}}function de(t,o,s){let c=e.TEXTURE_2D;(o.isDataArrayTexture||o.isCompressedArrayTexture)&&(c=e.TEXTURE_2D_ARRAY),o.isData3DTexture&&(c=e.TEXTURE_3D);let l=ce(t,o),u=o.source;n.bindTexture(c,t.__webglTexture,e.TEXTURE0+s);let f=r.get(u);if(u.version!==f.__version||l===!0){if(n.activeTexture(e.TEXTURE0+s),!(typeof ImageBitmap<`u`&&o.image instanceof ImageBitmap)){let t=Xo.getPrimaries(Xo.workingColorSpace),r=o.colorSpace===``?null:Xo.getPrimaries(o.colorSpace),i=o.colorSpace===``||t===r?e.NONE:e.BROWSER_DEFAULT_WEBGL;n.pixelStorei(e.UNPACK_FLIP_Y_WEBGL,o.flipY),n.pixelStorei(e.UNPACK_PREMULTIPLY_ALPHA_WEBGL,o.premultiplyAlpha),n.pixelStorei(e.UNPACK_COLORSPACE_CONVERSION_WEBGL,i)}n.pixelStorei(e.UNPACK_ALIGNMENT,o.unpackAlignment);let t=g(o.image,!1,i.maxTextureSize);t=we(o,t);let r=a.convert(o.format,o.colorSpace),p=a.convert(o.type),m=b(o.internalFormat,r,p,o.normalized,o.colorSpace,o.isVideoTexture);se(c,o);let h,y=o.mipmaps,C=o.isVideoTexture!==!0,w=f.__version===void 0||l===!0,T=u.dataReady,E=S(o,t);if(o.isDepthTexture)m=x(o.format===ea,o.type),w&&(C?n.texStorage2D(e.TEXTURE_2D,1,m,t.width,t.height):n.texImage2D(e.TEXTURE_2D,0,m,t.width,t.height,0,r,p,null));else if(o.isDataTexture)if(y.length>0){C&&w&&n.texStorage2D(e.TEXTURE_2D,E,m,y[0].width,y[0].height);for(let t=0,i=y.length;t<i;t++)h=y[t],C?T&&n.texSubImage2D(e.TEXTURE_2D,t,0,0,h.width,h.height,r,p,h.data):n.texImage2D(e.TEXTURE_2D,t,m,h.width,h.height,0,r,p,h.data);o.generateMipmaps=!1}else C?(w&&n.texStorage2D(e.TEXTURE_2D,E,m,t.width,t.height),T&&ue(o,t,r,p)):n.texImage2D(e.TEXTURE_2D,0,m,t.width,t.height,0,r,p,t.data);else if(o.isCompressedTexture)if(o.isCompressedArrayTexture){C&&w&&n.texStorage3D(e.TEXTURE_2D_ARRAY,E,m,y[0].width,y[0].height,t.depth);for(let i=0,a=y.length;i<a;i++)if(h=y[i],o.format!==1023)if(r!==null)if(C){if(T)if(o.layerUpdates.size>0){let t=Df(h.width,h.height,o.format,o.type);for(let a of o.layerUpdates){let o=h.data.subarray(a*t/h.data.BYTES_PER_ELEMENT,(a+1)*t/h.data.BYTES_PER_ELEMENT);n.compressedTexSubImage3D(e.TEXTURE_2D_ARRAY,i,0,0,a,h.width,h.height,1,r,o)}o.clearLayerUpdates()}else n.compressedTexSubImage3D(e.TEXTURE_2D_ARRAY,i,0,0,0,h.width,h.height,t.depth,r,h.data)}else n.compressedTexImage3D(e.TEXTURE_2D_ARRAY,i,m,h.width,h.height,t.depth,0,h.data,0,0);else R(`WebGLRenderer: Attempt to load unsupported compressed texture format in .uploadTexture()`);else C?T&&n.texSubImage3D(e.TEXTURE_2D_ARRAY,i,0,0,0,h.width,h.height,t.depth,r,p,h.data):n.texImage3D(e.TEXTURE_2D_ARRAY,i,m,h.width,h.height,t.depth,0,r,p,h.data)}else{C&&w&&n.texStorage2D(e.TEXTURE_2D,E,m,y[0].width,y[0].height);for(let t=0,i=y.length;t<i;t++)h=y[t],o.format===1023?C?T&&n.texSubImage2D(e.TEXTURE_2D,t,0,0,h.width,h.height,r,p,h.data):n.texImage2D(e.TEXTURE_2D,t,m,h.width,h.height,0,r,p,h.data):r===null?R(`WebGLRenderer: Attempt to load unsupported compressed texture format in .uploadTexture()`):C?T&&n.compressedTexSubImage2D(e.TEXTURE_2D,t,0,0,h.width,h.height,r,h.data):n.compressedTexImage2D(e.TEXTURE_2D,t,m,h.width,h.height,0,h.data)}else if(o.isDataArrayTexture)if(C){if(w&&n.texStorage3D(e.TEXTURE_2D_ARRAY,E,m,t.width,t.height,t.depth),T)if(o.layerUpdates.size>0){let i=Df(t.width,t.height,o.format,o.type);for(let a of o.layerUpdates){let o=t.data.subarray(a*i/t.data.BYTES_PER_ELEMENT,(a+1)*i/t.data.BYTES_PER_ELEMENT);n.texSubImage3D(e.TEXTURE_2D_ARRAY,0,0,0,a,t.width,t.height,1,r,p,o)}o.clearLayerUpdates()}else n.texSubImage3D(e.TEXTURE_2D_ARRAY,0,0,0,0,t.width,t.height,t.depth,r,p,t.data)}else n.texImage3D(e.TEXTURE_2D_ARRAY,0,m,t.width,t.height,t.depth,0,r,p,t.data);else if(o.isData3DTexture)C?(w&&n.texStorage3D(e.TEXTURE_3D,E,m,t.width,t.height,t.depth),T&&n.texSubImage3D(e.TEXTURE_3D,0,0,0,0,t.width,t.height,t.depth,r,p,t.data)):n.texImage3D(e.TEXTURE_3D,0,m,t.width,t.height,t.depth,0,r,p,t.data);else if(o.isFramebufferTexture){if(w)if(C)n.texStorage2D(e.TEXTURE_2D,E,m,t.width,t.height);else{let i=t.width,a=t.height;for(let t=0;t<E;t++)n.texImage2D(e.TEXTURE_2D,t,m,i,a,0,r,p,null),i>>=1,a>>=1}}else if(o.isHTMLTexture){if(`texElementImage2D`in e){let n=e.canvas;if(n.hasAttribute(`layoutsubtree`)||n.setAttribute(`layoutsubtree`,`true`),t.parentNode!==n){n.appendChild(t),d.add(o),n.onpaint=e=>{let t=e.changedElements;for(let e of d)t.includes(e.image)&&(e.needsUpdate=!0)},n.requestPaint();return}let r=e.RGBA,i=e.RGBA,a=e.UNSIGNED_BYTE;e.texElementImage2D(e.TEXTURE_2D,0,r,i,a,t),e.texParameteri(e.TEXTURE_2D,e.TEXTURE_MIN_FILTER,e.LINEAR),e.texParameteri(e.TEXTURE_2D,e.TEXTURE_WRAP_S,e.CLAMP_TO_EDGE),e.texParameteri(e.TEXTURE_2D,e.TEXTURE_WRAP_T,e.CLAMP_TO_EDGE)}}else if(y.length>0){if(C&&w){let t=I(y[0]);n.texStorage2D(e.TEXTURE_2D,E,m,t.width,t.height)}for(let t=0,i=y.length;t<i;t++)h=y[t],C?T&&n.texSubImage2D(e.TEXTURE_2D,t,0,0,r,p,h):n.texImage2D(e.TEXTURE_2D,t,m,r,p,h);o.generateMipmaps=!1}else if(C){if(w){let r=I(t);n.texStorage2D(e.TEXTURE_2D,E,m,r.width,r.height)}T&&n.texSubImage2D(e.TEXTURE_2D,0,0,0,r,p,t)}else n.texImage2D(e.TEXTURE_2D,0,m,r,p,t);_(o)&&v(c),f.__version=u.version,o.onUpdate&&o.onUpdate(o)}t.__version=o.version}function fe(t,o,s){if(o.image.length!==6)return;let c=ce(t,o),l=o.source;n.bindTexture(e.TEXTURE_CUBE_MAP,t.__webglTexture,e.TEXTURE0+s);let u=r.get(l);if(l.version!==u.__version||c===!0){n.activeTexture(e.TEXTURE0+s);let t=Xo.getPrimaries(Xo.workingColorSpace),r=o.colorSpace===``?null:Xo.getPrimaries(o.colorSpace),d=o.colorSpace===``||t===r?e.NONE:e.BROWSER_DEFAULT_WEBGL;n.pixelStorei(e.UNPACK_FLIP_Y_WEBGL,o.flipY),n.pixelStorei(e.UNPACK_PREMULTIPLY_ALPHA_WEBGL,o.premultiplyAlpha),n.pixelStorei(e.UNPACK_ALIGNMENT,o.unpackAlignment),n.pixelStorei(e.UNPACK_COLORSPACE_CONVERSION_WEBGL,d);let f=o.isCompressedTexture||o.image[0].isCompressedTexture,p=o.image[0]&&o.image[0].isDataTexture,m=[];for(let e=0;e<6;e++)!f&&!p?m[e]=g(o.image[e],!0,i.maxCubemapSize):m[e]=p?o.image[e].image:o.image[e],m[e]=we(o,m[e]);let h=m[0],y=a.convert(o.format,o.colorSpace),x=a.convert(o.type),C=b(o.internalFormat,y,x,o.normalized,o.colorSpace),w=o.isVideoTexture!==!0,T=u.__version===void 0||c===!0,E=l.dataReady,D=S(o,h);se(e.TEXTURE_CUBE_MAP,o);let O;if(f){w&&T&&n.texStorage2D(e.TEXTURE_CUBE_MAP,D,C,h.width,h.height);for(let t=0;t<6;t++){O=m[t].mipmaps;for(let r=0;r<O.length;r++){let i=O[r];o.format===1023?w?E&&n.texSubImage2D(e.TEXTURE_CUBE_MAP_POSITIVE_X+t,r,0,0,i.width,i.height,y,x,i.data):n.texImage2D(e.TEXTURE_CUBE_MAP_POSITIVE_X+t,r,C,i.width,i.height,0,y,x,i.data):y===null?R(`WebGLRenderer: Attempt to load unsupported compressed texture format in .setTextureCube()`):w?E&&n.compressedTexSubImage2D(e.TEXTURE_CUBE_MAP_POSITIVE_X+t,r,0,0,i.width,i.height,y,i.data):n.compressedTexImage2D(e.TEXTURE_CUBE_MAP_POSITIVE_X+t,r,C,i.width,i.height,0,i.data)}}}else{if(O=o.mipmaps,w&&T){O.length>0&&D++;let t=I(m[0]);n.texStorage2D(e.TEXTURE_CUBE_MAP,D,C,t.width,t.height)}for(let t=0;t<6;t++)if(p){w?E&&n.texSubImage2D(e.TEXTURE_CUBE_MAP_POSITIVE_X+t,0,0,0,m[t].width,m[t].height,y,x,m[t].data):n.texImage2D(e.TEXTURE_CUBE_MAP_POSITIVE_X+t,0,C,m[t].width,m[t].height,0,y,x,m[t].data);for(let r=0;r<O.length;r++){let i=O[r].image[t].image;w?E&&n.texSubImage2D(e.TEXTURE_CUBE_MAP_POSITIVE_X+t,r+1,0,0,i.width,i.height,y,x,i.data):n.texImage2D(e.TEXTURE_CUBE_MAP_POSITIVE_X+t,r+1,C,i.width,i.height,0,y,x,i.data)}}else{w?E&&n.texSubImage2D(e.TEXTURE_CUBE_MAP_POSITIVE_X+t,0,0,0,y,x,m[t]):n.texImage2D(e.TEXTURE_CUBE_MAP_POSITIVE_X+t,0,C,y,x,m[t]);for(let r=0;r<O.length;r++){let i=O[r];w?E&&n.texSubImage2D(e.TEXTURE_CUBE_MAP_POSITIVE_X+t,r+1,0,0,y,x,i.image[t]):n.texImage2D(e.TEXTURE_CUBE_MAP_POSITIVE_X+t,r+1,C,y,x,i.image[t])}}}_(o)&&v(e.TEXTURE_CUBE_MAP),u.__version=l.version,o.onUpdate&&o.onUpdate(o)}t.__version=o.version}function pe(t,i,o,c,l,u){let d=a.convert(o.format,o.colorSpace),f=a.convert(o.type),p=b(o.internalFormat,d,f,o.normalized,o.colorSpace),m=r.get(i),h=r.get(o);if(h.__renderTarget=i,!m.__hasExternalTextures){let t=Math.max(1,i.width>>u),r=Math.max(1,i.height>>u);l===e.TEXTURE_3D||l===e.TEXTURE_2D_ARRAY?n.texImage3D(l,u,p,t,r,i.depth,0,d,f,null):n.texImage2D(l,u,p,t,r,0,d,f,null)}n.bindFramebuffer(e.FRAMEBUFFER,t),Ce(i)?s.framebufferTexture2DMultisampleEXT(e.FRAMEBUFFER,c,l,h.__webglTexture,0,Se(i)):(l===e.TEXTURE_2D||l>=e.TEXTURE_CUBE_MAP_POSITIVE_X&&l<=e.TEXTURE_CUBE_MAP_NEGATIVE_Z)&&e.framebufferTexture2D(e.FRAMEBUFFER,c,l,h.__webglTexture,u),n.bindFramebuffer(e.FRAMEBUFFER,null)}function me(t,n,r){if(e.bindRenderbuffer(e.RENDERBUFFER,t),n.depthBuffer){let i=n.depthTexture,a=i&&i.isDepthTexture?i.type:null,o=x(n.stencilBuffer,a),c=n.stencilBuffer?e.DEPTH_STENCIL_ATTACHMENT:e.DEPTH_ATTACHMENT;Ce(n)?s.renderbufferStorageMultisampleEXT(e.RENDERBUFFER,Se(n),o,n.width,n.height):r?e.renderbufferStorageMultisample(e.RENDERBUFFER,Se(n),o,n.width,n.height):e.renderbufferStorage(e.RENDERBUFFER,o,n.width,n.height),e.framebufferRenderbuffer(e.FRAMEBUFFER,c,e.RENDERBUFFER,t)}else{let t=n.textures;for(let i=0;i<t.length;i++){let o=t[i],c=a.convert(o.format,o.colorSpace),l=a.convert(o.type),u=b(o.internalFormat,c,l,o.normalized,o.colorSpace);Ce(n)?s.renderbufferStorageMultisampleEXT(e.RENDERBUFFER,Se(n),u,n.width,n.height):r?e.renderbufferStorageMultisample(e.RENDERBUFFER,Se(n),u,n.width,n.height):e.renderbufferStorage(e.RENDERBUFFER,u,n.width,n.height)}}e.bindRenderbuffer(e.RENDERBUFFER,null)}function he(t,i,o){let c=i.isWebGLCubeRenderTarget===!0;if(n.bindFramebuffer(e.FRAMEBUFFER,t),!(i.depthTexture&&i.depthTexture.isDepthTexture))throw Error(`renderTarget.depthTexture must be an instance of THREE.DepthTexture`);let l=r.get(i.depthTexture);if(l.__renderTarget=i,(!l.__webglTexture||i.depthTexture.image.width!==i.width||i.depthTexture.image.height!==i.height)&&(i.depthTexture.image.width=i.width,i.depthTexture.image.height=i.height,i.depthTexture.needsUpdate=!0),c){if(l.__webglInit===void 0&&(l.__webglInit=!0,i.depthTexture.addEventListener(`dispose`,C)),l.__webglTexture===void 0){l.__webglTexture=e.createTexture(),n.bindTexture(e.TEXTURE_CUBE_MAP,l.__webglTexture),se(e.TEXTURE_CUBE_MAP,i.depthTexture);let t=a.convert(i.depthTexture.format),r=a.convert(i.depthTexture.type),o;i.depthTexture.format===1026?o=e.DEPTH_COMPONENT24:i.depthTexture.format===1027&&(o=e.DEPTH24_STENCIL8);for(let n=0;n<6;n++)e.texImage2D(e.TEXTURE_CUBE_MAP_POSITIVE_X+n,0,o,i.width,i.height,0,t,r,null)}}else ne(i.depthTexture,0);let u=l.__webglTexture,d=Se(i),f=c?e.TEXTURE_CUBE_MAP_POSITIVE_X+o:e.TEXTURE_2D,p=i.depthTexture.format===1027?e.DEPTH_STENCIL_ATTACHMENT:e.DEPTH_ATTACHMENT;if(i.depthTexture.format===1026)Ce(i)?s.framebufferTexture2DMultisampleEXT(e.FRAMEBUFFER,p,f,u,0,d):e.framebufferTexture2D(e.FRAMEBUFFER,p,f,u,0);else if(i.depthTexture.format===1027)Ce(i)?s.framebufferTexture2DMultisampleEXT(e.FRAMEBUFFER,p,f,u,0,d):e.framebufferTexture2D(e.FRAMEBUFFER,p,f,u,0);else throw Error(`Unknown depthTexture format`)}function ge(t){let i=r.get(t),a=t.isWebGLCubeRenderTarget===!0;if(i.__boundDepthTexture!==t.depthTexture){let e=t.depthTexture;if(i.__depthDisposeCallback&&i.__depthDisposeCallback(),e){let t=()=>{delete i.__boundDepthTexture,delete i.__depthDisposeCallback,e.removeEventListener(`dispose`,t)};e.addEventListener(`dispose`,t),i.__depthDisposeCallback=t}i.__boundDepthTexture=e}if(t.depthTexture&&!i.__autoAllocateDepthBuffer)if(a)for(let e=0;e<6;e++)he(i.__webglFramebuffer[e],t,e);else{let e=t.texture.mipmaps;e&&e.length>0?he(i.__webglFramebuffer[0],t,0):he(i.__webglFramebuffer,t,0)}else if(a){i.__webglDepthbuffer=[];for(let r=0;r<6;r++)if(n.bindFramebuffer(e.FRAMEBUFFER,i.__webglFramebuffer[r]),i.__webglDepthbuffer[r]===void 0)i.__webglDepthbuffer[r]=e.createRenderbuffer(),me(i.__webglDepthbuffer[r],t,!1);else{let n=t.stencilBuffer?e.DEPTH_STENCIL_ATTACHMENT:e.DEPTH_ATTACHMENT,a=i.__webglDepthbuffer[r];e.bindRenderbuffer(e.RENDERBUFFER,a),e.framebufferRenderbuffer(e.FRAMEBUFFER,n,e.RENDERBUFFER,a)}}else{let r=t.texture.mipmaps;if(r&&r.length>0?n.bindFramebuffer(e.FRAMEBUFFER,i.__webglFramebuffer[0]):n.bindFramebuffer(e.FRAMEBUFFER,i.__webglFramebuffer),i.__webglDepthbuffer===void 0)i.__webglDepthbuffer=e.createRenderbuffer(),me(i.__webglDepthbuffer,t,!1);else{let n=t.stencilBuffer?e.DEPTH_STENCIL_ATTACHMENT:e.DEPTH_ATTACHMENT,r=i.__webglDepthbuffer;e.bindRenderbuffer(e.RENDERBUFFER,r),e.framebufferRenderbuffer(e.FRAMEBUFFER,n,e.RENDERBUFFER,r)}}n.bindFramebuffer(e.FRAMEBUFFER,null)}function _e(t,n,i){let a=r.get(t);n!==void 0&&pe(a.__webglFramebuffer,t,t.texture,e.COLOR_ATTACHMENT0,e.TEXTURE_2D,0),i!==void 0&&ge(t)}function ve(t){let i=t.texture,s=r.get(t),c=r.get(i);t.addEventListener(`dispose`,w);let l=t.textures,u=t.isWebGLCubeRenderTarget===!0,d=l.length>1;if(d||(c.__webglTexture===void 0&&(c.__webglTexture=e.createTexture()),c.__version=i.version,o.memory.textures++),u){s.__webglFramebuffer=[];for(let t=0;t<6;t++)if(i.mipmaps&&i.mipmaps.length>0){s.__webglFramebuffer[t]=[];for(let n=0;n<i.mipmaps.length;n++)s.__webglFramebuffer[t][n]=e.createFramebuffer()}else s.__webglFramebuffer[t]=e.createFramebuffer()}else{if(i.mipmaps&&i.mipmaps.length>0){s.__webglFramebuffer=[];for(let t=0;t<i.mipmaps.length;t++)s.__webglFramebuffer[t]=e.createFramebuffer()}else s.__webglFramebuffer=e.createFramebuffer();if(d)for(let t=0,n=l.length;t<n;t++){let n=r.get(l[t]);n.__webglTexture===void 0&&(n.__webglTexture=e.createTexture(),o.memory.textures++)}if(t.samples>0&&Ce(t)===!1){s.__webglMultisampledFramebuffer=e.createFramebuffer(),s.__webglColorRenderbuffer=[],n.bindFramebuffer(e.FRAMEBUFFER,s.__webglMultisampledFramebuffer);for(let n=0;n<l.length;n++){let r=l[n];s.__webglColorRenderbuffer[n]=e.createRenderbuffer(),e.bindRenderbuffer(e.RENDERBUFFER,s.__webglColorRenderbuffer[n]);let i=a.convert(r.format,r.colorSpace),o=a.convert(r.type),c=b(r.internalFormat,i,o,r.normalized,r.colorSpace,t.isXRRenderTarget===!0),u=Se(t);e.renderbufferStorageMultisample(e.RENDERBUFFER,u,c,t.width,t.height),e.framebufferRenderbuffer(e.FRAMEBUFFER,e.COLOR_ATTACHMENT0+n,e.RENDERBUFFER,s.__webglColorRenderbuffer[n])}e.bindRenderbuffer(e.RENDERBUFFER,null),t.depthBuffer&&(s.__webglDepthRenderbuffer=e.createRenderbuffer(),me(s.__webglDepthRenderbuffer,t,!0)),n.bindFramebuffer(e.FRAMEBUFFER,null)}}if(u){n.bindTexture(e.TEXTURE_CUBE_MAP,c.__webglTexture),se(e.TEXTURE_CUBE_MAP,i);for(let n=0;n<6;n++)if(i.mipmaps&&i.mipmaps.length>0)for(let r=0;r<i.mipmaps.length;r++)pe(s.__webglFramebuffer[n][r],t,i,e.COLOR_ATTACHMENT0,e.TEXTURE_CUBE_MAP_POSITIVE_X+n,r);else pe(s.__webglFramebuffer[n],t,i,e.COLOR_ATTACHMENT0,e.TEXTURE_CUBE_MAP_POSITIVE_X+n,0);_(i)&&v(e.TEXTURE_CUBE_MAP),n.unbindTexture()}else if(d){for(let i=0,a=l.length;i<a;i++){let a=l[i],o=r.get(a),c=e.TEXTURE_2D;(t.isWebGL3DRenderTarget||t.isWebGLArrayRenderTarget)&&(c=t.isWebGL3DRenderTarget?e.TEXTURE_3D:e.TEXTURE_2D_ARRAY),n.bindTexture(c,o.__webglTexture),se(c,a),pe(s.__webglFramebuffer,t,a,e.COLOR_ATTACHMENT0+i,c,0),_(a)&&v(c)}n.unbindTexture()}else{let r=e.TEXTURE_2D;if((t.isWebGL3DRenderTarget||t.isWebGLArrayRenderTarget)&&(r=t.isWebGL3DRenderTarget?e.TEXTURE_3D:e.TEXTURE_2D_ARRAY),n.bindTexture(r,c.__webglTexture),se(r,i),i.mipmaps&&i.mipmaps.length>0)for(let n=0;n<i.mipmaps.length;n++)pe(s.__webglFramebuffer[n],t,i,e.COLOR_ATTACHMENT0,r,n);else pe(s.__webglFramebuffer,t,i,e.COLOR_ATTACHMENT0,r,0);_(i)&&v(r),n.unbindTexture()}t.depthBuffer&&ge(t)}function ye(e){let t=e.textures;for(let i=0,a=t.length;i<a;i++){let a=t[i];if(_(a)){let t=y(e),i=r.get(a).__webglTexture;n.bindTexture(t,i),v(t),n.unbindTexture()}}}let be=[],P=[];function xe(t){if(t.samples>0){if(Ce(t)===!1){let i=t.textures,a=t.width,o=t.height,s=e.COLOR_BUFFER_BIT,l=t.stencilBuffer?e.DEPTH_STENCIL_ATTACHMENT:e.DEPTH_ATTACHMENT,u=r.get(t),d=i.length>1;if(d)for(let t=0;t<i.length;t++)n.bindFramebuffer(e.FRAMEBUFFER,u.__webglMultisampledFramebuffer),e.framebufferRenderbuffer(e.FRAMEBUFFER,e.COLOR_ATTACHMENT0+t,e.RENDERBUFFER,null),n.bindFramebuffer(e.FRAMEBUFFER,u.__webglFramebuffer),e.framebufferTexture2D(e.DRAW_FRAMEBUFFER,e.COLOR_ATTACHMENT0+t,e.TEXTURE_2D,null,0);n.bindFramebuffer(e.READ_FRAMEBUFFER,u.__webglMultisampledFramebuffer);let f=t.texture.mipmaps;f&&f.length>0?n.bindFramebuffer(e.DRAW_FRAMEBUFFER,u.__webglFramebuffer[0]):n.bindFramebuffer(e.DRAW_FRAMEBUFFER,u.__webglFramebuffer);for(let n=0;n<i.length;n++){if(t.resolveDepthBuffer&&(t.depthBuffer&&(s|=e.DEPTH_BUFFER_BIT),t.stencilBuffer&&t.resolveStencilBuffer&&(s|=e.STENCIL_BUFFER_BIT)),d){e.framebufferRenderbuffer(e.READ_FRAMEBUFFER,e.COLOR_ATTACHMENT0,e.RENDERBUFFER,u.__webglColorRenderbuffer[n]);let t=r.get(i[n]).__webglTexture;e.framebufferTexture2D(e.DRAW_FRAMEBUFFER,e.COLOR_ATTACHMENT0,e.TEXTURE_2D,t,0)}e.blitFramebuffer(0,0,a,o,0,0,a,o,s,e.NEAREST),c===!0&&(be.length=0,P.length=0,be.push(e.COLOR_ATTACHMENT0+n),t.depthBuffer&&t.resolveDepthBuffer===!1&&(be.push(l),P.push(l),e.invalidateFramebuffer(e.DRAW_FRAMEBUFFER,P)),e.invalidateFramebuffer(e.READ_FRAMEBUFFER,be))}if(n.bindFramebuffer(e.READ_FRAMEBUFFER,null),n.bindFramebuffer(e.DRAW_FRAMEBUFFER,null),d)for(let t=0;t<i.length;t++){n.bindFramebuffer(e.FRAMEBUFFER,u.__webglMultisampledFramebuffer),e.framebufferRenderbuffer(e.FRAMEBUFFER,e.COLOR_ATTACHMENT0+t,e.RENDERBUFFER,u.__webglColorRenderbuffer[t]);let a=r.get(i[t]).__webglTexture;n.bindFramebuffer(e.FRAMEBUFFER,u.__webglFramebuffer),e.framebufferTexture2D(e.DRAW_FRAMEBUFFER,e.COLOR_ATTACHMENT0+t,e.TEXTURE_2D,a,0)}n.bindFramebuffer(e.DRAW_FRAMEBUFFER,u.__webglMultisampledFramebuffer)}else if(t.depthBuffer&&t.resolveDepthBuffer===!1&&c){let n=t.stencilBuffer?e.DEPTH_STENCIL_ATTACHMENT:e.DEPTH_ATTACHMENT;e.invalidateFramebuffer(e.DRAW_FRAMEBUFFER,[n])}}}function Se(e){return Math.min(i.maxSamples,e.samples)}function Ce(e){let n=r.get(e);return e.samples>0&&t.has(`WEBGL_multisampled_render_to_texture`)===!0&&n.__useRenderToTexture!==!1}function F(e){let t=o.render.frame;u.get(e)!==t&&(u.set(e,t),e.update())}function we(e,t){let n=e.colorSpace,r=e.format,i=e.type;return e.isCompressedTexture===!0||e.isVideoTexture===!0||n!==`srgb-linear`&&n!==``&&(Xo.getTransfer(n)===`srgb`?(r!==1023||i!==1009)&&R(`WebGLTextures: sRGB encoded textures have to use RGBAFormat and UnsignedByteType.`):z(`WebGLTextures: Unsupported texture color space:`,n)),t}function I(e){return typeof HTMLImageElement<`u`&&e instanceof HTMLImageElement?(l.width=e.naturalWidth||e.width,l.height=e.naturalHeight||e.height):typeof VideoFrame<`u`&&e instanceof VideoFrame?(l.width=e.displayWidth,l.height=e.displayHeight):(l.width=e.width,l.height=e.height),l}this.allocateTextureUnit=te,this.resetTextureUnits=k,this.getTextureUnits=A,this.setTextureUnits=ee,this.setTexture2D=ne,this.setTexture2DArray=M,this.setTexture3D=re,this.setTextureCube=N,this.rebindTextures=_e,this.setupRenderTarget=ve,this.updateRenderTargetMipmap=ye,this.updateMultisampleRenderTarget=xe,this.setupDepthRenderbuffer=ge,this.setupFrameBufferTexture=pe,this.useMultisampledRTT=Ce,this.isReversedDepthBuffer=function(){return n.buffers.depth.getReversed()}}function Mh(e,t){function n(n,r=``){let i,a=Xo.getTransfer(r);if(n===1009)return e.UNSIGNED_BYTE;if(n===1017)return e.UNSIGNED_SHORT_4_4_4_4;if(n===1018)return e.UNSIGNED_SHORT_5_5_5_1;if(n===35902)return e.UNSIGNED_INT_5_9_9_9_REV;if(n===35899)return e.UNSIGNED_INT_10F_11F_11F_REV;if(n===1010)return e.BYTE;if(n===1011)return e.SHORT;if(n===1012)return e.UNSIGNED_SHORT;if(n===1013)return e.INT;if(n===1014)return e.UNSIGNED_INT;if(n===1015)return e.FLOAT;if(n===1016)return e.HALF_FLOAT;if(n===1021)return e.ALPHA;if(n===1022)return e.RGB;if(n===1023)return e.RGBA;if(n===1026)return e.DEPTH_COMPONENT;if(n===1027)return e.DEPTH_STENCIL;if(n===1028)return e.RED;if(n===1029)return e.RED_INTEGER;if(n===1030)return e.RG;if(n===1031)return e.RG_INTEGER;if(n===1033)return e.RGBA_INTEGER;if(n===33776||n===33777||n===33778||n===33779)if(a===`srgb`)if(i=t.get(`WEBGL_compressed_texture_s3tc_srgb`),i!==null){if(n===33776)return i.COMPRESSED_SRGB_S3TC_DXT1_EXT;if(n===33777)return i.COMPRESSED_SRGB_ALPHA_S3TC_DXT1_EXT;if(n===33778)return i.COMPRESSED_SRGB_ALPHA_S3TC_DXT3_EXT;if(n===33779)return i.COMPRESSED_SRGB_ALPHA_S3TC_DXT5_EXT}else return null;else if(i=t.get(`WEBGL_compressed_texture_s3tc`),i!==null){if(n===33776)return i.COMPRESSED_RGB_S3TC_DXT1_EXT;if(n===33777)return i.COMPRESSED_RGBA_S3TC_DXT1_EXT;if(n===33778)return i.COMPRESSED_RGBA_S3TC_DXT3_EXT;if(n===33779)return i.COMPRESSED_RGBA_S3TC_DXT5_EXT}else return null;if(n===35840||n===35841||n===35842||n===35843)if(i=t.get(`WEBGL_compressed_texture_pvrtc`),i!==null){if(n===35840)return i.COMPRESSED_RGB_PVRTC_4BPPV1_IMG;if(n===35841)return i.COMPRESSED_RGB_PVRTC_2BPPV1_IMG;if(n===35842)return i.COMPRESSED_RGBA_PVRTC_4BPPV1_IMG;if(n===35843)return i.COMPRESSED_RGBA_PVRTC_2BPPV1_IMG}else return null;if(n===36196||n===37492||n===37496||n===37488||n===37489||n===37490||n===37491)if(i=t.get(`WEBGL_compressed_texture_etc`),i!==null){if(n===36196||n===37492)return a===`srgb`?i.COMPRESSED_SRGB8_ETC2:i.COMPRESSED_RGB8_ETC2;if(n===37496)return a===`srgb`?i.COMPRESSED_SRGB8_ALPHA8_ETC2_EAC:i.COMPRESSED_RGBA8_ETC2_EAC;if(n===37488)return i.COMPRESSED_R11_EAC;if(n===37489)return i.COMPRESSED_SIGNED_R11_EAC;if(n===37490)return i.COMPRESSED_RG11_EAC;if(n===37491)return i.COMPRESSED_SIGNED_RG11_EAC}else return null;if(n===37808||n===37809||n===37810||n===37811||n===37812||n===37813||n===37814||n===37815||n===37816||n===37817||n===37818||n===37819||n===37820||n===37821)if(i=t.get(`WEBGL_compressed_texture_astc`),i!==null){if(n===37808)return a===`srgb`?i.COMPRESSED_SRGB8_ALPHA8_ASTC_4x4_KHR:i.COMPRESSED_RGBA_ASTC_4x4_KHR;if(n===37809)return a===`srgb`?i.COMPRESSED_SRGB8_ALPHA8_ASTC_5x4_KHR:i.COMPRESSED_RGBA_ASTC_5x4_KHR;if(n===37810)return a===`srgb`?i.COMPRESSED_SRGB8_ALPHA8_ASTC_5x5_KHR:i.COMPRESSED_RGBA_ASTC_5x5_KHR;if(n===37811)return a===`srgb`?i.COMPRESSED_SRGB8_ALPHA8_ASTC_6x5_KHR:i.COMPRESSED_RGBA_ASTC_6x5_KHR;if(n===37812)return a===`srgb`?i.COMPRESSED_SRGB8_ALPHA8_ASTC_6x6_KHR:i.COMPRESSED_RGBA_ASTC_6x6_KHR;if(n===37813)return a===`srgb`?i.COMPRESSED_SRGB8_ALPHA8_ASTC_8x5_KHR:i.COMPRESSED_RGBA_ASTC_8x5_KHR;if(n===37814)return a===`srgb`?i.COMPRESSED_SRGB8_ALPHA8_ASTC_8x6_KHR:i.COMPRESSED_RGBA_ASTC_8x6_KHR;if(n===37815)return a===`srgb`?i.COMPRESSED_SRGB8_ALPHA8_ASTC_8x8_KHR:i.COMPRESSED_RGBA_ASTC_8x8_KHR;if(n===37816)return a===`srgb`?i.COMPRESSED_SRGB8_ALPHA8_ASTC_10x5_KHR:i.COMPRESSED_RGBA_ASTC_10x5_KHR;if(n===37817)return a===`srgb`?i.COMPRESSED_SRGB8_ALPHA8_ASTC_10x6_KHR:i.COMPRESSED_RGBA_ASTC_10x6_KHR;if(n===37818)return a===`srgb`?i.COMPRESSED_SRGB8_ALPHA8_ASTC_10x8_KHR:i.COMPRESSED_RGBA_ASTC_10x8_KHR;if(n===37819)return a===`srgb`?i.COMPRESSED_SRGB8_ALPHA8_ASTC_10x10_KHR:i.COMPRESSED_RGBA_ASTC_10x10_KHR;if(n===37820)return a===`srgb`?i.COMPRESSED_SRGB8_ALPHA8_ASTC_12x10_KHR:i.COMPRESSED_RGBA_ASTC_12x10_KHR;if(n===37821)return a===`srgb`?i.COMPRESSED_SRGB8_ALPHA8_ASTC_12x12_KHR:i.COMPRESSED_RGBA_ASTC_12x12_KHR}else return null;if(n===36492||n===36494||n===36495)if(i=t.get(`EXT_texture_compression_bptc`),i!==null){if(n===36492)return a===`srgb`?i.COMPRESSED_SRGB_ALPHA_BPTC_UNORM_EXT:i.COMPRESSED_RGBA_BPTC_UNORM_EXT;if(n===36494)return i.COMPRESSED_RGB_BPTC_SIGNED_FLOAT_EXT;if(n===36495)return i.COMPRESSED_RGB_BPTC_UNSIGNED_FLOAT_EXT}else return null;if(n===36283||n===36284||n===36285||n===36286)if(i=t.get(`EXT_texture_compression_rgtc`),i!==null){if(n===36283)return i.COMPRESSED_RED_RGTC1_EXT;if(n===36284)return i.COMPRESSED_SIGNED_RED_RGTC1_EXT;if(n===36285)return i.COMPRESSED_RED_GREEN_RGTC2_EXT;if(n===36286)return i.COMPRESSED_SIGNED_RED_GREEN_RGTC2_EXT}else return null;return n===1020?e.UNSIGNED_INT_24_8:e[n]===void 0?null:e[n]}return{convert:n}}var Nh=`
void main() {

	gl_Position = vec4( position, 1.0 );

}`,Ph=`
uniform sampler2DArray depthColor;
uniform float depthWidth;
uniform float depthHeight;

void main() {

	vec2 coord = vec2( gl_FragCoord.x / depthWidth, gl_FragCoord.y / depthHeight );

	if ( coord.x >= 1.0 ) {

		gl_FragDepth = texture( depthColor, vec3( coord.x - 1.0, coord.y, 1 ) ).r;

	} else {

		gl_FragDepth = texture( depthColor, vec3( coord.x, coord.y, 0 ) ).r;

	}

}`,Fh=class{constructor(){this.texture=null,this.mesh=null,this.depthNear=0,this.depthFar=0}init(e,t){if(this.texture===null){let n=new pu(e.texture);(e.depthNear!==t.depthNear||e.depthFar!==t.depthFar)&&(this.depthNear=e.depthNear,this.depthFar=e.depthFar),this.texture=n}}getMesh(e){if(this.texture!==null&&this.mesh===null){let t=e.cameras[0].viewport,n=new ud({vertexShader:Nh,fragmentShader:Ph,uniforms:{depthColor:{value:this.texture},depthWidth:{value:t.z},depthHeight:{value:t.w}}});this.mesh=new kl(new Yu(20,20),n)}return this.mesh}reset(){this.texture=null,this.mesh=null}getDepthTexture(){return this.texture}},Ih=class extends go{constructor(e,t){super();let n=this,r=null,i=1,a=null,o=`local-floor`,s=1,c=null,l=null,u=null,d=null,f=null,p=null,m=typeof XRWebGLBinding<`u`,h=new Fh,g={},_=t.getContextAttributes(),v=null,y=null,b=[],x=[],S=new V,C=null,w=new Gd;w.viewport=new ss;let T=new Gd;T.viewport=new ss;let E=[w,T],D=new Qd,O=null,k=null;this.cameraAutoUpdate=!0,this.enabled=!1,this.isPresenting=!1,this.getController=function(e){let t=b[e];return t===void 0&&(t=new Hs,b[e]=t),t.getTargetRaySpace()},this.getControllerGrip=function(e){let t=b[e];return t===void 0&&(t=new Hs,b[e]=t),t.getGripSpace()},this.getHand=function(e){let t=b[e];return t===void 0&&(t=new Hs,b[e]=t),t.getHandSpace()};function A(e){let t=x.indexOf(e.inputSource);if(t===-1)return;let n=b[t];n!==void 0&&(n.update(e.inputSource,e.frame,c||a),n.dispatchEvent({type:e.type,data:e.inputSource}))}function ee(){r.removeEventListener(`select`,A),r.removeEventListener(`selectstart`,A),r.removeEventListener(`selectend`,A),r.removeEventListener(`squeeze`,A),r.removeEventListener(`squeezestart`,A),r.removeEventListener(`squeezeend`,A),r.removeEventListener(`end`,ee),r.removeEventListener(`inputsourceschange`,te);for(let e=0;e<b.length;e++){let t=x[e];t!==null&&(x[e]=null,b[e].disconnect(t))}O=null,k=null,h.reset();for(let e in g)delete g[e];e.setRenderTarget(v),f=null,d=null,u=null,r=null,y=null,oe.stop(),n.isPresenting=!1,e.setPixelRatio(C),e.setSize(S.width,S.height,!1),n.dispatchEvent({type:`sessionend`})}this.setFramebufferScaleFactor=function(e){i=e,n.isPresenting===!0&&R(`WebXRManager: Cannot change framebuffer scale while presenting.`)},this.setReferenceSpaceType=function(e){o=e,n.isPresenting===!0&&R(`WebXRManager: Cannot change reference space type while presenting.`)},this.getReferenceSpace=function(){return c||a},this.setReferenceSpace=function(e){c=e},this.getBaseLayer=function(){return d===null?f:d},this.getBinding=function(){return u===null&&m&&(u=new XRWebGLBinding(r,t)),u},this.getFrame=function(){return p},this.getSession=function(){return r},this.setSession=async function(l){if(r=l,r!==null){if(v=e.getRenderTarget(),r.addEventListener(`select`,A),r.addEventListener(`selectstart`,A),r.addEventListener(`selectend`,A),r.addEventListener(`squeeze`,A),r.addEventListener(`squeezestart`,A),r.addEventListener(`squeezeend`,A),r.addEventListener(`end`,ee),r.addEventListener(`inputsourceschange`,te),_.xrCompatible!==!0&&await t.makeXRCompatible(),C=e.getPixelRatio(),e.getSize(S),m&&`createProjectionLayer`in XRWebGLBinding.prototype){let n=null,a=null,o=null;_.depth&&(o=_.stencil?t.DEPTH24_STENCIL8:t.DEPTH_COMPONENT24,n=_.stencil?ea:$i,a=_.stencil?qi:Hi);let s={colorFormat:t.RGBA8,depthFormat:o,scaleFactor:i};u=this.getBinding(),d=u.createProjectionLayer(s),r.updateRenderState({layers:[d]}),e.setPixelRatio(1),e.setSize(d.textureWidth,d.textureHeight,!1),y=new ls(d.textureWidth,d.textureHeight,{format:Qi,type:Li,depthTexture:new du(d.textureWidth,d.textureHeight,a,void 0,void 0,void 0,void 0,void 0,void 0,n),stencilBuffer:_.stencil,colorSpace:e.outputColorSpace,samples:_.antialias?4:0,resolveDepthBuffer:d.ignoreDepthValues===!1,resolveStencilBuffer:d.ignoreDepthValues===!1})}else{let n={antialias:_.antialias,alpha:!0,depth:_.depth,stencil:_.stencil,framebufferScaleFactor:i};f=new XRWebGLLayer(r,t,n),r.updateRenderState({baseLayer:f}),e.setPixelRatio(1),e.setSize(f.framebufferWidth,f.framebufferHeight,!1),y=new ls(f.framebufferWidth,f.framebufferHeight,{format:Qi,type:Li,colorSpace:e.outputColorSpace,stencilBuffer:_.stencil,resolveDepthBuffer:f.ignoreDepthValues===!1,resolveStencilBuffer:f.ignoreDepthValues===!1})}y.isXRRenderTarget=!0,this.setFoveation(s),c=null,a=await r.requestReferenceSpace(o),oe.setContext(r),oe.start(),n.isPresenting=!0,n.dispatchEvent({type:`sessionstart`})}},this.getEnvironmentBlendMode=function(){if(r!==null)return r.environmentBlendMode},this.getDepthTexture=function(){return h.getDepthTexture()};function te(e){for(let t=0;t<e.removed.length;t++){let n=e.removed[t],r=x.indexOf(n);r>=0&&(x[r]=null,b[r].disconnect(n))}for(let t=0;t<e.added.length;t++){let n=e.added[t],r=x.indexOf(n);if(r===-1){for(let e=0;e<b.length;e++)if(e>=x.length){x.push(n),r=e;break}else if(x[e]===null){x[e]=n,r=e;break}if(r===-1)break}let i=b[r];i&&i.connect(n)}}let j=new H,ne=new H;function M(e,t,n){j.setFromMatrixPosition(t.matrixWorld),ne.setFromMatrixPosition(n.matrixWorld);let r=j.distanceTo(ne),i=t.projectionMatrix.elements,a=n.projectionMatrix.elements,o=i[14]/(i[10]-1),s=i[14]/(i[10]+1),c=(i[9]+1)/i[5],l=(i[9]-1)/i[5],u=(i[8]-1)/i[0],d=(a[8]+1)/a[0],f=o*u,p=o*d,m=r/(-u+d),h=m*-u;if(t.matrixWorld.decompose(e.position,e.quaternion,e.scale),e.translateX(h),e.translateZ(m),e.matrixWorld.compose(e.position,e.quaternion,e.scale),e.matrixWorldInverse.copy(e.matrixWorld).invert(),i[10]===-1)e.projectionMatrix.copy(t.projectionMatrix),e.projectionMatrixInverse.copy(t.projectionMatrixInverse);else{let t=o+m,n=s+m,i=f-h,a=p+(r-h),u=c*s/n*t,d=l*s/n*t;e.projectionMatrix.makePerspective(i,a,u,d,t,n),e.projectionMatrixInverse.copy(e.projectionMatrix).invert()}}function re(e,t){t===null?e.matrixWorld.copy(e.matrix):e.matrixWorld.multiplyMatrices(t.matrixWorld,e.matrix),e.matrixWorldInverse.copy(e.matrixWorld).invert()}this.updateCamera=function(e){if(r===null)return;let t=e.near,n=e.far;h.texture!==null&&(h.depthNear>0&&(t=h.depthNear),h.depthFar>0&&(n=h.depthFar)),D.near=T.near=w.near=t,D.far=T.far=w.far=n,(O!==D.near||k!==D.far)&&(r.updateRenderState({depthNear:D.near,depthFar:D.far}),O=D.near,k=D.far),D.layers.mask=e.layers.mask|6,w.layers.mask=D.layers.mask&-5,T.layers.mask=D.layers.mask&-3;let i=e.parent,a=D.cameras;re(D,i);for(let e=0;e<a.length;e++)re(a[e],i);a.length===2?M(D,w,T):D.projectionMatrix.copy(w.projectionMatrix),N(e,D,i)};function N(e,t,n){n===null?e.matrix.copy(t.matrixWorld):(e.matrix.copy(n.matrixWorld),e.matrix.invert(),e.matrix.multiply(t.matrixWorld)),e.matrix.decompose(e.position,e.quaternion,e.scale),e.updateMatrixWorld(!0),e.projectionMatrix.copy(t.projectionMatrix),e.projectionMatrixInverse.copy(t.projectionMatrixInverse),e.isPerspectiveCamera&&(e.fov=bo*2*Math.atan(1/e.projectionMatrix.elements[5]),e.zoom=1)}this.getCamera=function(){return D},this.getFoveation=function(){if(!(d===null&&f===null))return s},this.setFoveation=function(e){s=e,d!==null&&(d.fixedFoveation=e),f!==null&&f.fixedFoveation!==void 0&&(f.fixedFoveation=e)},this.hasDepthSensing=function(){return h.texture!==null},this.getDepthSensingMesh=function(){return h.getMesh(D)},this.getCameraTexture=function(e){return g[e]};let ie=null;function ae(t,i){if(l=i.getViewerPose(c||a),p=i,l!==null){let t=l.views;f!==null&&(e.setRenderTargetFramebuffer(y,f.framebuffer),e.setRenderTarget(y));let i=!1;t.length!==D.cameras.length&&(D.cameras.length=0,i=!0);for(let n=0;n<t.length;n++){let r=t[n],a=null;if(f!==null)a=f.getViewport(r);else{let t=u.getViewSubImage(d,r);a=t.viewport,n===0&&(e.setRenderTargetTextures(y,t.colorTexture,t.depthStencilTexture),e.setRenderTarget(y))}let o=E[n];o===void 0&&(o=new Gd,o.layers.enable(n),o.viewport=new ss,E[n]=o),o.matrix.fromArray(r.transform.matrix),o.matrix.decompose(o.position,o.quaternion,o.scale),o.projectionMatrix.fromArray(r.projectionMatrix),o.projectionMatrixInverse.copy(o.projectionMatrix).invert(),o.viewport.set(a.x,a.y,a.width,a.height),n===0&&(D.matrix.copy(o.matrix),D.matrix.decompose(D.position,D.quaternion,D.scale)),i===!0&&D.cameras.push(o)}let a=r.enabledFeatures;if(a&&a.includes(`depth-sensing`)&&r.depthUsage==`gpu-optimized`&&m){u=n.getBinding();let e=u.getDepthInformation(t[0]);e&&e.isValid&&e.texture&&h.init(e,r.renderState)}if(a&&a.includes(`camera-access`)&&m){e.state.unbindTexture(),u=n.getBinding();for(let e=0;e<t.length;e++){let n=t[e].camera;if(n){let e=g[n];e||(e=new pu,g[n]=e);let t=u.getCameraImage(n);e.sourceTexture=t}}}}for(let e=0;e<b.length;e++){let t=x[e],n=b[e];t!==null&&n!==void 0&&n.update(t,i,c||a)}ie&&ie(t,i),i.detectedPlanes&&n.dispatchEvent({type:`planesdetected`,data:i}),p=null}let oe=new kf;oe.setAnimationLoop(ae),this.setAnimationLoop=function(e){ie=e},this.dispose=function(){}}},Lh=new fs,Rh=new U;Rh.set(-1,0,0,0,1,0,0,0,1);function zh(e,t){function n(e,t){e.matrixAutoUpdate===!0&&e.updateMatrix(),t.value.copy(e.matrix)}function r(t,n){n.color.getRGB(t.fogColor.value,od(e)),n.isFog?(t.fogNear.value=n.near,t.fogFar.value=n.far):n.isFogExp2&&(t.fogDensity.value=n.density)}function i(e,t,n,r,i){t.isNodeMaterial?t.uniformsNeedUpdate=!1:t.isMeshBasicMaterial?a(e,t):t.isMeshLambertMaterial?(a(e,t),t.envMap&&(e.envMapIntensity.value=t.envMapIntensity)):t.isMeshToonMaterial?(a(e,t),d(e,t)):t.isMeshPhongMaterial?(a(e,t),u(e,t),t.envMap&&(e.envMapIntensity.value=t.envMapIntensity)):t.isMeshStandardMaterial?(a(e,t),f(e,t),t.isMeshPhysicalMaterial&&p(e,t,i)):t.isMeshMatcapMaterial?(a(e,t),m(e,t)):t.isMeshDepthMaterial?a(e,t):t.isMeshDistanceMaterial?(a(e,t),h(e,t)):t.isMeshNormalMaterial?a(e,t):t.isLineBasicMaterial?(o(e,t),t.isLineDashedMaterial&&s(e,t)):t.isPointsMaterial?c(e,t,n,r):t.isSpriteMaterial?l(e,t):t.isShadowMaterial?(e.color.value.copy(t.color),e.opacity.value=t.opacity):t.isShaderMaterial&&(t.uniformsNeedUpdate=!1)}function a(e,r){e.opacity.value=r.opacity,r.color&&e.diffuse.value.copy(r.color),r.emissive&&e.emissive.value.copy(r.emissive).multiplyScalar(r.emissiveIntensity),r.map&&(e.map.value=r.map,n(r.map,e.mapTransform)),r.alphaMap&&(e.alphaMap.value=r.alphaMap,n(r.alphaMap,e.alphaMapTransform)),r.bumpMap&&(e.bumpMap.value=r.bumpMap,n(r.bumpMap,e.bumpMapTransform),e.bumpScale.value=r.bumpScale,r.side===1&&(e.bumpScale.value*=-1)),r.normalMap&&(e.normalMap.value=r.normalMap,n(r.normalMap,e.normalMapTransform),e.normalScale.value.copy(r.normalScale),r.side===1&&e.normalScale.value.negate()),r.displacementMap&&(e.displacementMap.value=r.displacementMap,n(r.displacementMap,e.displacementMapTransform),e.displacementScale.value=r.displacementScale,e.displacementBias.value=r.displacementBias),r.emissiveMap&&(e.emissiveMap.value=r.emissiveMap,n(r.emissiveMap,e.emissiveMapTransform)),r.specularMap&&(e.specularMap.value=r.specularMap,n(r.specularMap,e.specularMapTransform)),r.alphaTest>0&&(e.alphaTest.value=r.alphaTest);let i=t.get(r),a=i.envMap,o=i.envMapRotation;a&&(e.envMap.value=a,e.envMapRotation.value.setFromMatrix4(Lh.makeRotationFromEuler(o)).transpose(),a.isCubeTexture&&a.isRenderTargetTexture===!1&&e.envMapRotation.value.premultiply(Rh),e.reflectivity.value=r.reflectivity,e.ior.value=r.ior,e.refractionRatio.value=r.refractionRatio),r.lightMap&&(e.lightMap.value=r.lightMap,e.lightMapIntensity.value=r.lightMapIntensity,n(r.lightMap,e.lightMapTransform)),r.aoMap&&(e.aoMap.value=r.aoMap,e.aoMapIntensity.value=r.aoMapIntensity,n(r.aoMap,e.aoMapTransform))}function o(e,t){e.diffuse.value.copy(t.color),e.opacity.value=t.opacity,t.map&&(e.map.value=t.map,n(t.map,e.mapTransform))}function s(e,t){e.dashSize.value=t.dashSize,e.totalSize.value=t.dashSize+t.gapSize,e.scale.value=t.scale}function c(e,t,r,i){e.diffuse.value.copy(t.color),e.opacity.value=t.opacity,e.size.value=t.size*r,e.scale.value=i*.5,t.map&&(e.map.value=t.map,n(t.map,e.uvTransform)),t.alphaMap&&(e.alphaMap.value=t.alphaMap,n(t.alphaMap,e.alphaMapTransform)),t.alphaTest>0&&(e.alphaTest.value=t.alphaTest)}function l(e,t){e.diffuse.value.copy(t.color),e.opacity.value=t.opacity,e.rotation.value=t.rotation,t.map&&(e.map.value=t.map,n(t.map,e.mapTransform)),t.alphaMap&&(e.alphaMap.value=t.alphaMap,n(t.alphaMap,e.alphaMapTransform)),t.alphaTest>0&&(e.alphaTest.value=t.alphaTest)}function u(e,t){e.specular.value.copy(t.specular),e.shininess.value=Math.max(t.shininess,1e-4)}function d(e,t){t.gradientMap&&(e.gradientMap.value=t.gradientMap)}function f(e,t){e.metalness.value=t.metalness,t.metalnessMap&&(e.metalnessMap.value=t.metalnessMap,n(t.metalnessMap,e.metalnessMapTransform)),e.roughness.value=t.roughness,t.roughnessMap&&(e.roughnessMap.value=t.roughnessMap,n(t.roughnessMap,e.roughnessMapTransform)),t.envMap&&(e.envMapIntensity.value=t.envMapIntensity)}function p(e,t,r){e.ior.value=t.ior,t.sheen>0&&(e.sheenColor.value.copy(t.sheenColor).multiplyScalar(t.sheen),e.sheenRoughness.value=t.sheenRoughness,t.sheenColorMap&&(e.sheenColorMap.value=t.sheenColorMap,n(t.sheenColorMap,e.sheenColorMapTransform)),t.sheenRoughnessMap&&(e.sheenRoughnessMap.value=t.sheenRoughnessMap,n(t.sheenRoughnessMap,e.sheenRoughnessMapTransform))),t.clearcoat>0&&(e.clearcoat.value=t.clearcoat,e.clearcoatRoughness.value=t.clearcoatRoughness,t.clearcoatMap&&(e.clearcoatMap.value=t.clearcoatMap,n(t.clearcoatMap,e.clearcoatMapTransform)),t.clearcoatRoughnessMap&&(e.clearcoatRoughnessMap.value=t.clearcoatRoughnessMap,n(t.clearcoatRoughnessMap,e.clearcoatRoughnessMapTransform)),t.clearcoatNormalMap&&(e.clearcoatNormalMap.value=t.clearcoatNormalMap,n(t.clearcoatNormalMap,e.clearcoatNormalMapTransform),e.clearcoatNormalScale.value.copy(t.clearcoatNormalScale),t.side===1&&e.clearcoatNormalScale.value.negate())),t.dispersion>0&&(e.dispersion.value=t.dispersion),t.iridescence>0&&(e.iridescence.value=t.iridescence,e.iridescenceIOR.value=t.iridescenceIOR,e.iridescenceThicknessMinimum.value=t.iridescenceThicknessRange[0],e.iridescenceThicknessMaximum.value=t.iridescenceThicknessRange[1],t.iridescenceMap&&(e.iridescenceMap.value=t.iridescenceMap,n(t.iridescenceMap,e.iridescenceMapTransform)),t.iridescenceThicknessMap&&(e.iridescenceThicknessMap.value=t.iridescenceThicknessMap,n(t.iridescenceThicknessMap,e.iridescenceThicknessMapTransform))),t.transmission>0&&(e.transmission.value=t.transmission,e.transmissionSamplerMap.value=r.texture,e.transmissionSamplerSize.value.set(r.width,r.height),t.transmissionMap&&(e.transmissionMap.value=t.transmissionMap,n(t.transmissionMap,e.transmissionMapTransform)),e.thickness.value=t.thickness,t.thicknessMap&&(e.thicknessMap.value=t.thicknessMap,n(t.thicknessMap,e.thicknessMapTransform)),e.attenuationDistance.value=t.attenuationDistance,e.attenuationColor.value.copy(t.attenuationColor)),t.anisotropy>0&&(e.anisotropyVector.value.set(t.anisotropy*Math.cos(t.anisotropyRotation),t.anisotropy*Math.sin(t.anisotropyRotation)),t.anisotropyMap&&(e.anisotropyMap.value=t.anisotropyMap,n(t.anisotropyMap,e.anisotropyMapTransform))),e.specularIntensity.value=t.specularIntensity,e.specularColor.value.copy(t.specularColor),t.specularColorMap&&(e.specularColorMap.value=t.specularColorMap,n(t.specularColorMap,e.specularColorMapTransform)),t.specularIntensityMap&&(e.specularIntensityMap.value=t.specularIntensityMap,n(t.specularIntensityMap,e.specularIntensityMapTransform))}function m(e,t){t.matcap&&(e.matcap.value=t.matcap)}function h(e,n){let r=t.get(n).light;e.referencePosition.value.setFromMatrixPosition(r.matrixWorld),e.nearDistance.value=r.shadow.camera.near,e.farDistance.value=r.shadow.camera.far}return{refreshFogUniforms:r,refreshMaterialUniforms:i}}function Bh(e,t,n,r){let i={},a={},o=[],s=e.getParameter(e.MAX_UNIFORM_BUFFER_BINDINGS);function c(e,t){let n=t.program;r.uniformBlockBinding(e,n)}function l(e,n){let o=i[e.id];o===void 0&&(m(e),o=u(e),i[e.id]=o,e.addEventListener(`dispose`,g));let s=n.program;r.updateUBOMapping(e,s);let c=t.render.frame;a[e.id]!==c&&(f(e),a[e.id]=c)}function u(t){let n=d();t.__bindingPointIndex=n;let r=e.createBuffer(),i=t.__size,a=t.usage;return e.bindBuffer(e.UNIFORM_BUFFER,r),e.bufferData(e.UNIFORM_BUFFER,i,a),e.bindBuffer(e.UNIFORM_BUFFER,null),e.bindBufferBase(e.UNIFORM_BUFFER,n,r),r}function d(){for(let e=0;e<s;e++)if(o.indexOf(e)===-1)return o.push(e),e;return z(`WebGLRenderer: Maximum number of simultaneously usable uniforms groups reached.`),0}function f(t){let n=i[t.id],r=t.uniforms,a=t.__cache;e.bindBuffer(e.UNIFORM_BUFFER,n);for(let t=0,n=r.length;t<n;t++){let n=Array.isArray(r[t])?r[t]:[r[t]];for(let r=0,i=n.length;r<i;r++){let i=n[r];if(p(i,t,r,a)===!0){let t=i.__offset,n=Array.isArray(i.value)?i.value:[i.value],r=0;for(let a=0;a<n.length;a++){let o=n[a],s=h(o);typeof o==`number`||typeof o==`boolean`?(i.__data[0]=o,e.bufferSubData(e.UNIFORM_BUFFER,t+r,i.__data)):o.isMatrix3?(i.__data[0]=o.elements[0],i.__data[1]=o.elements[1],i.__data[2]=o.elements[2],i.__data[3]=0,i.__data[4]=o.elements[3],i.__data[5]=o.elements[4],i.__data[6]=o.elements[5],i.__data[7]=0,i.__data[8]=o.elements[6],i.__data[9]=o.elements[7],i.__data[10]=o.elements[8],i.__data[11]=0):ArrayBuffer.isView(o)?i.__data.set(new o.constructor(o.buffer,o.byteOffset,i.__data.length)):(o.toArray(i.__data,r),r+=s.storage/Float32Array.BYTES_PER_ELEMENT)}e.bufferSubData(e.UNIFORM_BUFFER,t,i.__data)}}}e.bindBuffer(e.UNIFORM_BUFFER,null)}function p(e,t,n,r){let i=e.value,a=t+`_`+n;if(r[a]===void 0)return typeof i==`number`||typeof i==`boolean`?r[a]=i:ArrayBuffer.isView(i)?r[a]=i.slice():r[a]=i.clone(),!0;{let e=r[a];if(typeof i==`number`||typeof i==`boolean`){if(e!==i)return r[a]=i,!0}else if(ArrayBuffer.isView(i))return!0;else if(e.equals(i)===!1)return e.copy(i),!0}return!1}function m(e){let t=e.uniforms,n=0;for(let e=0,r=t.length;e<r;e++){let r=Array.isArray(t[e])?t[e]:[t[e]];for(let e=0,t=r.length;e<t;e++){let t=r[e],i=Array.isArray(t.value)?t.value:[t.value];for(let e=0,r=i.length;e<r;e++){let r=i[e],a=h(r),o=n%16,s=o%a.boundary,c=o+s;n+=s,c!==0&&16-c<a.storage&&(n+=16-c),t.__data=new Float32Array(a.storage/Float32Array.BYTES_PER_ELEMENT),t.__offset=n,n+=a.storage}}}let r=n%16;return r>0&&(n+=16-r),e.__size=n,e.__cache={},this}function h(e){let t={boundary:0,storage:0};return typeof e==`number`||typeof e==`boolean`?(t.boundary=4,t.storage=4):e.isVector2?(t.boundary=8,t.storage=8):e.isVector3||e.isColor?(t.boundary=16,t.storage=12):e.isVector4?(t.boundary=16,t.storage=16):e.isMatrix3?(t.boundary=48,t.storage=48):e.isMatrix4?(t.boundary=64,t.storage=64):e.isTexture?R(`WebGLRenderer: Texture samplers can not be part of an uniforms group.`):ArrayBuffer.isView(e)?(t.boundary=16,t.storage=e.byteLength):R(`WebGLRenderer: Unsupported uniform value type.`,e),t}function g(t){let n=t.target;n.removeEventListener(`dispose`,g);let r=o.indexOf(n.__bindingPointIndex);o.splice(r,1),e.deleteBuffer(i[n.id]),delete i[n.id],delete a[n.id]}function _(){for(let t in i)e.deleteBuffer(i[t]);o=[],i={},a={}}return{bind:c,update:l,dispose:_}}var Vh=new Uint16Array([12469,15057,12620,14925,13266,14620,13807,14376,14323,13990,14545,13625,14713,13328,14840,12882,14931,12528,14996,12233,15039,11829,15066,11525,15080,11295,15085,10976,15082,10705,15073,10495,13880,14564,13898,14542,13977,14430,14158,14124,14393,13732,14556,13410,14702,12996,14814,12596,14891,12291,14937,11834,14957,11489,14958,11194,14943,10803,14921,10506,14893,10278,14858,9960,14484,14039,14487,14025,14499,13941,14524,13740,14574,13468,14654,13106,14743,12678,14818,12344,14867,11893,14889,11509,14893,11180,14881,10751,14852,10428,14812,10128,14765,9754,14712,9466,14764,13480,14764,13475,14766,13440,14766,13347,14769,13070,14786,12713,14816,12387,14844,11957,14860,11549,14868,11215,14855,10751,14825,10403,14782,10044,14729,9651,14666,9352,14599,9029,14967,12835,14966,12831,14963,12804,14954,12723,14936,12564,14917,12347,14900,11958,14886,11569,14878,11247,14859,10765,14828,10401,14784,10011,14727,9600,14660,9289,14586,8893,14508,8533,15111,12234,15110,12234,15104,12216,15092,12156,15067,12010,15028,11776,14981,11500,14942,11205,14902,10752,14861,10393,14812,9991,14752,9570,14682,9252,14603,8808,14519,8445,14431,8145,15209,11449,15208,11451,15202,11451,15190,11438,15163,11384,15117,11274,15055,10979,14994,10648,14932,10343,14871,9936,14803,9532,14729,9218,14645,8742,14556,8381,14461,8020,14365,7603,15273,10603,15272,10607,15267,10619,15256,10631,15231,10614,15182,10535,15118,10389,15042,10167,14963,9787,14883,9447,14800,9115,14710,8665,14615,8318,14514,7911,14411,7507,14279,7198,15314,9675,15313,9683,15309,9712,15298,9759,15277,9797,15229,9773,15166,9668,15084,9487,14995,9274,14898,8910,14800,8539,14697,8234,14590,7790,14479,7409,14367,7067,14178,6621,15337,8619,15337,8631,15333,8677,15325,8769,15305,8871,15264,8940,15202,8909,15119,8775,15022,8565,14916,8328,14804,8009,14688,7614,14569,7287,14448,6888,14321,6483,14088,6171,15350,7402,15350,7419,15347,7480,15340,7613,15322,7804,15287,7973,15229,8057,15148,8012,15046,7846,14933,7611,14810,7357,14682,7069,14552,6656,14421,6316,14251,5948,14007,5528,15356,5942,15356,5977,15353,6119,15348,6294,15332,6551,15302,6824,15249,7044,15171,7122,15070,7050,14949,6861,14818,6611,14679,6349,14538,6067,14398,5651,14189,5311,13935,4958,15359,4123,15359,4153,15356,4296,15353,4646,15338,5160,15311,5508,15263,5829,15188,6042,15088,6094,14966,6001,14826,5796,14678,5543,14527,5287,14377,4985,14133,4586,13869,4257,15360,1563,15360,1642,15358,2076,15354,2636,15341,3350,15317,4019,15273,4429,15203,4732,15105,4911,14981,4932,14836,4818,14679,4621,14517,4386,14359,4156,14083,3795,13808,3437,15360,122,15360,137,15358,285,15355,636,15344,1274,15322,2177,15281,2765,15215,3223,15120,3451,14995,3569,14846,3567,14681,3466,14511,3305,14344,3121,14037,2800,13753,2467,15360,0,15360,1,15359,21,15355,89,15346,253,15325,479,15287,796,15225,1148,15133,1492,15008,1749,14856,1882,14685,1886,14506,1783,14324,1608,13996,1398,13702,1183]),Hh=null;function Uh(){return Hh===null&&(Hh=new Ml(Vh,16,16,ra,Wi),Hh.name=`DFG_LUT`,Hh.minFilter=Pi,Hh.magFilter=Pi,Hh.wrapS=ki,Hh.wrapT=ki,Hh.generateMipmaps=!1,Hh.needsUpdate=!0),Hh}var Wh=class{constructor(e={}){let{canvas:t=so(),context:n=null,depth:r=!0,stencil:i=!1,alpha:a=!1,antialias:o=!1,premultipliedAlpha:s=!0,preserveDrawingBuffer:c=!1,powerPreference:l=`default`,failIfMajorPerformanceCaveat:u=!1,reversedDepthBuffer:d=!1,outputBufferType:f=Li}=e;this.isWebGLRenderer=!0;let p;if(n!==null){if(typeof WebGLRenderingContext<`u`&&n instanceof WebGLRenderingContext)throw Error(`THREE.WebGLRenderer: WebGL 1 is not supported since r163.`);p=n.getContextAttributes().alpha}else p=a;let m=f,h=new Set([aa,ia,na]),g=new Set([Li,Hi,Bi,qi,Gi,Ki]),_=new Uint32Array(4),v=new Int32Array(4),y=new H,b=null,x=null,S=[],C=[],w=null;this.domElement=t,this.debug={checkShaderErrors:!0,onShaderError:null},this.autoClear=!0,this.autoClearColor=!0,this.autoClearDepth=!0,this.autoClearStencil=!0,this.sortObjects=!0,this.clippingPlanes=[],this.localClippingEnabled=!1,this.toneMapping=0,this.toneMappingExposure=1,this.transmissionResolutionScale=1;let T=this,E=!1,D=null;this._outputColorSpace=Za;let O=0,k=0,A=null,ee=-1,te=null,j=new ss,ne=new ss,M=null,re=new W(0),N=0,ie=t.width,ae=t.height,oe=1,se=null,ce=null,le=new ss(0,0,ie,ae),ue=new ss(0,0,ie,ae),de=!1,fe=new Yl,pe=!1,me=!1,he=new fs,ge=new H,_e=new ss,ve={background:null,fog:null,environment:null,overrideMaterial:null,isScene:!0},ye=!1;function be(){return A===null?oe:1}let P=n;function xe(e,n){return t.getContext(e,n)}try{let e={alpha:!0,depth:r,stencil:i,antialias:o,premultipliedAlpha:s,preserveDrawingBuffer:c,powerPreference:l,failIfMajorPerformanceCaveat:u};if(`setAttribute`in t&&t.setAttribute(`data-engine`,`three.js r184`),t.addEventListener(`webglcontextlost`,We,!1),t.addEventListener(`webglcontextrestored`,Ge,!1),t.addEventListener(`webglcontextcreationerror`,Ke,!1),P===null){let t=`webgl2`;if(P=xe(t,e),P===null)throw xe(t)?Error(`Error creating WebGL context with your selected attributes.`):Error(`Error creating WebGL context.`)}}catch(e){throw z(`WebGLRenderer: `+e.message),e}let Se,Ce,F,we,I,L,Te,Ee,De,Oe,ke,Ae,je,Me,Ne,Pe,Fe,Ie,Le,Re,ze,Be,Ve;function He(){Se=new cp(P),Se.init(),ze=new Mh(P,Se),Ce=new Rf(P,Se,e,ze),F=new Ah(P,Se),Ce.reversedDepthBuffer&&d&&F.buffers.depth.setReversed(!0),we=new dp(P),I=new uh,L=new jh(P,Se,F,I,Ce,ze,we),Te=new sp(T),Ee=new Af(P),Be=new If(P,Ee),De=new lp(P,Ee,we,Be),Oe=new pp(P,De,Ee,Be,we),Ie=new fp(P,Ce,L),Ne=new zf(I),ke=new lh(T,Te,Se,Ce,Be,Ne),Ae=new zh(T,I),je=new mh,Me=new xh(Se),Fe=new Ff(T,Te,F,Oe,p,s),Pe=new kh(T,Oe,Ce),Ve=new Bh(P,we,Ce,F),Le=new Lf(P,Se,we),Re=new up(P,Se,we),we.programs=ke.programs,T.capabilities=Ce,T.extensions=Se,T.properties=I,T.renderLists=je,T.shadowMap=Pe,T.state=F,T.info=we}He(),m!==1009&&(w=new hp(m,t.width,t.height,r,i));let Ue=new Ih(T,P);this.xr=Ue,this.getContext=function(){return P},this.getContextAttributes=function(){return P.getContextAttributes()},this.forceContextLoss=function(){let e=Se.get(`WEBGL_lose_context`);e&&e.loseContext()},this.forceContextRestore=function(){let e=Se.get(`WEBGL_lose_context`);e&&e.restoreContext()},this.getPixelRatio=function(){return oe},this.setPixelRatio=function(e){e!==void 0&&(oe=e,this.setSize(ie,ae,!1))},this.getSize=function(e){return e.set(ie,ae)},this.setSize=function(e,n,r=!0){if(Ue.isPresenting){R(`WebGLRenderer: Can't change size while VR device is presenting.`);return}ie=e,ae=n,t.width=Math.floor(e*oe),t.height=Math.floor(n*oe),r===!0&&(t.style.width=e+`px`,t.style.height=n+`px`),w!==null&&w.setSize(t.width,t.height),this.setViewport(0,0,e,n)},this.getDrawingBufferSize=function(e){return e.set(ie*oe,ae*oe).floor()},this.setDrawingBufferSize=function(e,n,r){ie=e,ae=n,oe=r,t.width=Math.floor(e*r),t.height=Math.floor(n*r),this.setViewport(0,0,e,n)},this.setEffects=function(e){if(m===1009){z(`THREE.WebGLRenderer: setEffects() requires outputBufferType set to HalfFloatType or FloatType.`);return}if(e){for(let t=0;t<e.length;t++)if(e[t].isOutputPass===!0){R(`THREE.WebGLRenderer: OutputPass is not needed in setEffects(). Tone mapping and color space conversion are applied automatically.`);break}}w.setEffects(e||[])},this.getCurrentViewport=function(e){return e.copy(j)},this.getViewport=function(e){return e.copy(le)},this.setViewport=function(e,t,n,r){e.isVector4?le.set(e.x,e.y,e.z,e.w):le.set(e,t,n,r),F.viewport(j.copy(le).multiplyScalar(oe).round())},this.getScissor=function(e){return e.copy(ue)},this.setScissor=function(e,t,n,r){e.isVector4?ue.set(e.x,e.y,e.z,e.w):ue.set(e,t,n,r),F.scissor(ne.copy(ue).multiplyScalar(oe).round())},this.getScissorTest=function(){return de},this.setScissorTest=function(e){F.setScissorTest(de=e)},this.setOpaqueSort=function(e){se=e},this.setTransparentSort=function(e){ce=e},this.getClearColor=function(e){return e.copy(Fe.getClearColor())},this.setClearColor=function(){Fe.setClearColor(...arguments)},this.getClearAlpha=function(){return Fe.getClearAlpha()},this.setClearAlpha=function(){Fe.setClearAlpha(...arguments)},this.clear=function(e=!0,t=!0,n=!0){let r=0;if(e){let e=!1;if(A!==null){let t=A.texture.format;e=h.has(t)}if(e){let e=A.texture.type,t=g.has(e),n=Fe.getClearColor(),r=Fe.getClearAlpha(),i=n.r,a=n.g,o=n.b;t?(_[0]=i,_[1]=a,_[2]=o,_[3]=r,P.clearBufferuiv(P.COLOR,0,_)):(v[0]=i,v[1]=a,v[2]=o,v[3]=r,P.clearBufferiv(P.COLOR,0,v))}else r|=P.COLOR_BUFFER_BIT}t&&(r|=P.DEPTH_BUFFER_BIT,this.state.buffers.depth.setMask(!0)),n&&(r|=P.STENCIL_BUFFER_BIT,this.state.buffers.stencil.setMask(4294967295)),r!==0&&P.clear(r)},this.clearColor=function(){this.clear(!0,!1,!1)},this.clearDepth=function(){this.clear(!1,!0,!1)},this.clearStencil=function(){this.clear(!1,!1,!0)},this.setNodesHandler=function(e){e.setRenderer(this),D=e},this.dispose=function(){t.removeEventListener(`webglcontextlost`,We,!1),t.removeEventListener(`webglcontextrestored`,Ge,!1),t.removeEventListener(`webglcontextcreationerror`,Ke,!1),Fe.dispose(),je.dispose(),Me.dispose(),I.dispose(),Te.dispose(),Oe.dispose(),Be.dispose(),Ve.dispose(),ke.dispose(),Ue.dispose(),Ue.removeEventListener(`sessionstart`,$e),Ue.removeEventListener(`sessionend`,et),tt.stop()};function We(e){e.preventDefault(),uo(`WebGLRenderer: Context Lost.`),E=!0}function Ge(){uo(`WebGLRenderer: Context Restored.`),E=!1;let e=we.autoReset,t=Pe.enabled,n=Pe.autoUpdate,r=Pe.needsUpdate,i=Pe.type;He(),we.autoReset=e,Pe.enabled=t,Pe.autoUpdate=n,Pe.needsUpdate=r,Pe.type=i}function Ke(e){z(`WebGLRenderer: A WebGL context could not be created. Reason: `,e.statusMessage)}function qe(e){let t=e.target;t.removeEventListener(`dispose`,qe),Je(t)}function Je(e){Ye(e),I.remove(e)}function Ye(e){let t=I.get(e).programs;t!==void 0&&(t.forEach(function(e){ke.releaseProgram(e)}),e.isShaderMaterial&&ke.releaseShaderCache(e))}this.renderBufferDirect=function(e,t,n,r,i,a){t===null&&(t=ve);let o=i.isMesh&&i.matrixWorld.determinant()<0,s=dt(e,t,n,r,i);F.setMaterial(r,o);let c=n.index,l=1;if(r.wireframe===!0){if(c=De.getWireframeAttribute(n),c===void 0)return;l=2}let u=n.drawRange,d=n.attributes.position,f=u.start*l,p=(u.start+u.count)*l;a!==null&&(f=Math.max(f,a.start*l),p=Math.min(p,(a.start+a.count)*l)),c===null?d!=null&&(f=Math.max(f,0),p=Math.min(p,d.count)):(f=Math.max(f,0),p=Math.min(p,c.count));let m=p-f;if(m<0||m===1/0)return;Be.setup(i,r,s,n,c);let h,g=Le;if(c!==null&&(h=Ee.get(c),g=Re,g.setIndex(h)),i.isMesh)r.wireframe===!0?(F.setLineWidth(r.wireframeLinewidth*be()),g.setMode(P.LINES)):g.setMode(P.TRIANGLES);else if(i.isLine){let e=r.linewidth;e===void 0&&(e=1),F.setLineWidth(e*be()),i.isLineSegments?g.setMode(P.LINES):i.isLineLoop?g.setMode(P.LINE_LOOP):g.setMode(P.LINE_STRIP)}else i.isPoints?g.setMode(P.POINTS):i.isSprite&&g.setMode(P.TRIANGLES);if(i.isBatchedMesh)if(Se.get(`WEBGL_multi_draw`))g.renderMultiDraw(i._multiDrawStarts,i._multiDrawCounts,i._multiDrawCount);else{let e=i._multiDrawStarts,t=i._multiDrawCounts,n=i._multiDrawCount,a=c?Ee.get(c).bytesPerElement:1,o=I.get(r).currentProgram.getUniforms();for(let r=0;r<n;r++)o.setValue(P,`_gl_DrawID`,r),g.render(e[r]/a,t[r])}else if(i.isInstancedMesh)g.renderInstances(f,m,i.count);else if(n.isInstancedBufferGeometry){let e=n._maxInstanceCount===void 0?1/0:n._maxInstanceCount,t=Math.min(n.instanceCount,e);g.renderInstances(f,m,t)}else g.render(f,m)};function Xe(e,t,n){e.transparent===!0&&e.side===2&&e.forceSinglePass===!1?(e.side=1,e.needsUpdate=!0,st(e,t,n),e.side=0,e.needsUpdate=!0,st(e,t,n),e.side=2):st(e,t,n)}this.compile=function(e,t,n=null){n===null&&(n=e),x=Me.get(n),x.init(t),C.push(x),n.traverseVisible(function(e){e.isLight&&e.layers.test(t.layers)&&(x.pushLight(e),e.castShadow&&x.pushShadow(e))}),e!==n&&e.traverseVisible(function(e){e.isLight&&e.layers.test(t.layers)&&(x.pushLight(e),e.castShadow&&x.pushShadow(e))}),x.setupLights();let r=new Set;return e.traverse(function(e){if(!(e.isMesh||e.isPoints||e.isLine||e.isSprite))return;let t=e.material;if(t)if(Array.isArray(t))for(let i=0;i<t.length;i++){let a=t[i];Xe(a,n,e),r.add(a)}else Xe(t,n,e),r.add(t)}),x=C.pop(),r},this.compileAsync=function(e,t,n=null){let r=this.compile(e,t,n);return new Promise(t=>{function n(){if(r.forEach(function(e){I.get(e).currentProgram.isReady()&&r.delete(e)}),r.size===0){t(e);return}setTimeout(n,10)}Se.get(`KHR_parallel_shader_compile`)===null?setTimeout(n,10):n()})};let Ze=null;function Qe(e){Ze&&Ze(e)}function $e(){tt.stop()}function et(){tt.start()}let tt=new kf;tt.setAnimationLoop(Qe),typeof self<`u`&&tt.setContext(self),this.setAnimationLoop=function(e){Ze=e,Ue.setAnimationLoop(e),e===null?tt.stop():tt.start()},Ue.addEventListener(`sessionstart`,$e),Ue.addEventListener(`sessionend`,et),this.render=function(e,t){if(t!==void 0&&t.isCamera!==!0){z(`WebGLRenderer.render: camera is not an instance of THREE.Camera.`);return}if(E===!0)return;D!==null&&D.renderStart(e,t);let n=Ue.enabled===!0&&Ue.isPresenting===!0,r=w!==null&&(A===null||n)&&w.begin(T,A);if(e.matrixWorldAutoUpdate===!0&&e.updateMatrixWorld(),t.parent===null&&t.matrixWorldAutoUpdate===!0&&t.updateMatrixWorld(),Ue.enabled===!0&&Ue.isPresenting===!0&&(w===null||w.isCompositing()===!1)&&(Ue.cameraAutoUpdate===!0&&Ue.updateCamera(t),t=Ue.getCamera()),e.isScene===!0&&e.onBeforeRender(T,e,t,A),x=Me.get(e,C.length),x.init(t),x.state.textureUnits=L.getTextureUnits(),C.push(x),he.multiplyMatrices(t.projectionMatrix,t.matrixWorldInverse),fe.setFromProjectionMatrix(he,ro,t.reversedDepth),me=this.localClippingEnabled,pe=Ne.init(this.clippingPlanes,me),b=je.get(e,S.length),b.init(),S.push(b),Ue.enabled===!0&&Ue.isPresenting===!0){let e=T.xr.getDepthSensingMesh();e!==null&&nt(e,t,-1/0,T.sortObjects)}nt(e,t,0,T.sortObjects),b.finish(),T.sortObjects===!0&&b.sort(se,ce),ye=Ue.enabled===!1||Ue.isPresenting===!1||Ue.hasDepthSensing()===!1,ye&&Fe.addToRenderList(b,e),this.info.render.frame++,pe===!0&&Ne.beginShadows();let i=x.state.shadowsArray;if(Pe.render(i,e,t),pe===!0&&Ne.endShadows(),this.info.autoReset===!0&&this.info.reset(),(r&&w.hasRenderPass())===!1){let n=b.opaque,r=b.transmissive;if(x.setupLights(),t.isArrayCamera){let i=t.cameras;if(r.length>0)for(let t=0,a=i.length;t<a;t++){let a=i[t];it(n,r,e,a)}ye&&Fe.render(e);for(let t=0,n=i.length;t<n;t++){let n=i[t];rt(b,e,n,n.viewport)}}else r.length>0&&it(n,r,e,t),ye&&Fe.render(e),rt(b,e,t)}A!==null&&k===0&&(L.updateMultisampleRenderTarget(A),L.updateRenderTargetMipmap(A)),r&&w.end(T),e.isScene===!0&&e.onAfterRender(T,e,t),Be.resetDefaultState(),ee=-1,te=null,C.pop(),C.length>0?(x=C[C.length-1],L.setTextureUnits(x.state.textureUnits),pe===!0&&Ne.setGlobalState(T.clippingPlanes,x.state.camera)):x=null,S.pop(),b=S.length>0?S[S.length-1]:null,D!==null&&D.renderEnd()};function nt(e,t,n,r){if(e.visible===!1)return;if(e.layers.test(t.layers)){if(e.isGroup)n=e.renderOrder;else if(e.isLOD)e.autoUpdate===!0&&e.update(t);else if(e.isLightProbeGrid)x.pushLightProbeGrid(e);else if(e.isLight)x.pushLight(e),e.castShadow&&x.pushShadow(e);else if(e.isSprite){if(!e.frustumCulled||fe.intersectsSprite(e)){r&&_e.setFromMatrixPosition(e.matrixWorld).applyMatrix4(he);let t=Oe.update(e),i=e.material;i.visible&&b.push(e,t,i,n,_e.z,null)}}else if((e.isMesh||e.isLine||e.isPoints)&&(!e.frustumCulled||fe.intersectsObject(e))){let t=Oe.update(e),i=e.material;if(r&&(e.boundingSphere===void 0?(t.boundingSphere===null&&t.computeBoundingSphere(),_e.copy(t.boundingSphere.center)):(e.boundingSphere===null&&e.computeBoundingSphere(),_e.copy(e.boundingSphere.center)),_e.applyMatrix4(e.matrixWorld).applyMatrix4(he)),Array.isArray(i)){let r=t.groups;for(let a=0,o=r.length;a<o;a++){let o=r[a],s=i[o.materialIndex];s&&s.visible&&b.push(e,t,s,n,_e.z,o)}}else i.visible&&b.push(e,t,i,n,_e.z,null)}}let i=e.children;for(let e=0,a=i.length;e<a;e++)nt(i[e],t,n,r)}function rt(e,t,n,r){let{opaque:i,transmissive:a,transparent:o}=e;x.setupLightsView(n),pe===!0&&Ne.setGlobalState(T.clippingPlanes,n),r&&F.viewport(j.copy(r)),i.length>0&&at(i,t,n),a.length>0&&at(a,t,n),o.length>0&&at(o,t,n),F.buffers.depth.setTest(!0),F.buffers.depth.setMask(!0),F.buffers.color.setMask(!0),F.setPolygonOffset(!1)}function it(e,t,n,r){if((n.isScene===!0?n.overrideMaterial:null)!==null)return;if(x.state.transmissionRenderTarget[r.id]===void 0){let e=Se.has(`EXT_color_buffer_half_float`)||Se.has(`EXT_color_buffer_float`);x.state.transmissionRenderTarget[r.id]=new ls(1,1,{generateMipmaps:!0,type:e?Wi:Li,minFilter:Ii,samples:Math.max(4,Ce.samples),stencilBuffer:i,resolveDepthBuffer:!1,resolveStencilBuffer:!1,colorSpace:Xo.workingColorSpace})}let a=x.state.transmissionRenderTarget[r.id],o=r.viewport||j;a.setSize(o.z*T.transmissionResolutionScale,o.w*T.transmissionResolutionScale);let s=T.getRenderTarget(),c=T.getActiveCubeFace(),l=T.getActiveMipmapLevel();T.setRenderTarget(a),T.getClearColor(re),N=T.getClearAlpha(),N<1&&T.setClearColor(16777215,.5),T.clear(),ye&&Fe.render(n);let u=T.toneMapping;T.toneMapping=0;let d=r.viewport;if(r.viewport!==void 0&&(r.viewport=void 0),x.setupLightsView(r),pe===!0&&Ne.setGlobalState(T.clippingPlanes,r),at(e,n,r),L.updateMultisampleRenderTarget(a),L.updateRenderTargetMipmap(a),Se.has(`WEBGL_multisampled_render_to_texture`)===!1){let e=!1;for(let i=0,a=t.length;i<a;i++){let{object:a,geometry:o,material:s,group:c}=t[i];if(s.side===2&&a.layers.test(r.layers)){let t=s.side;s.side=1,s.needsUpdate=!0,ot(a,n,r,o,s,c),s.side=t,s.needsUpdate=!0,e=!0}}e===!0&&(L.updateMultisampleRenderTarget(a),L.updateRenderTargetMipmap(a))}T.setRenderTarget(s,c,l),T.setClearColor(re,N),d!==void 0&&(r.viewport=d),T.toneMapping=u}function at(e,t,n){let r=t.isScene===!0?t.overrideMaterial:null;for(let i=0,a=e.length;i<a;i++){let a=e[i],{object:o,geometry:s,group:c}=a,l=a.material;l.allowOverride===!0&&r!==null&&(l=r),o.layers.test(n.layers)&&ot(o,t,n,s,l,c)}}function ot(e,t,n,r,i,a){e.onBeforeRender(T,t,n,r,i,a),e.modelViewMatrix.multiplyMatrices(n.matrixWorldInverse,e.matrixWorld),e.normalMatrix.getNormalMatrix(e.modelViewMatrix),i.onBeforeRender(T,t,n,r,e,a),i.transparent===!0&&i.side===2&&i.forceSinglePass===!1?(i.side=1,i.needsUpdate=!0,T.renderBufferDirect(n,t,r,i,e,a),i.side=0,i.needsUpdate=!0,T.renderBufferDirect(n,t,r,i,e,a),i.side=2):T.renderBufferDirect(n,t,r,i,e,a),e.onAfterRender(T,t,n,r,i,a)}function st(e,t,n){t.isScene!==!0&&(t=ve);let r=I.get(e),i=x.state.lights,a=x.state.shadowsArray,o=i.state.version,s=ke.getParameters(e,i.state,a,t,n,x.state.lightProbeGridArray),c=ke.getProgramCacheKey(s),l=r.programs;r.environment=e.isMeshStandardMaterial||e.isMeshLambertMaterial||e.isMeshPhongMaterial?t.environment:null,r.fog=t.fog;let u=e.isMeshStandardMaterial||e.isMeshLambertMaterial&&!e.envMap||e.isMeshPhongMaterial&&!e.envMap;r.envMap=Te.get(e.envMap||r.environment,u),r.envMapRotation=r.environment!==null&&e.envMap===null?t.environmentRotation:e.envMapRotation,l===void 0&&(e.addEventListener(`dispose`,qe),l=new Map,r.programs=l);let d=l.get(c);if(d!==void 0){if(r.currentProgram===d&&r.lightsStateVersion===o)return lt(e,s),d}else s.uniforms=ke.getUniforms(e),D!==null&&e.isNodeMaterial&&D.build(e,n,s),e.onBeforeCompile(s,T),d=ke.acquireProgram(s,c),l.set(c,d),r.uniforms=s.uniforms;let f=r.uniforms;return(!e.isShaderMaterial&&!e.isRawShaderMaterial||e.clipping===!0)&&(f.clippingPlanes=Ne.uniform),lt(e,s),r.needsLights=pt(e),r.lightsStateVersion=o,r.needsLights&&(f.ambientLightColor.value=i.state.ambient,f.lightProbe.value=i.state.probe,f.directionalLights.value=i.state.directional,f.directionalLightShadows.value=i.state.directionalShadow,f.spotLights.value=i.state.spot,f.spotLightShadows.value=i.state.spotShadow,f.rectAreaLights.value=i.state.rectArea,f.ltc_1.value=i.state.rectAreaLTC1,f.ltc_2.value=i.state.rectAreaLTC2,f.pointLights.value=i.state.point,f.pointLightShadows.value=i.state.pointShadow,f.hemisphereLights.value=i.state.hemi,f.directionalShadowMatrix.value=i.state.directionalShadowMatrix,f.spotLightMatrix.value=i.state.spotLightMatrix,f.spotLightMap.value=i.state.spotLightMap,f.pointShadowMatrix.value=i.state.pointShadowMatrix),r.lightProbeGrid=x.state.lightProbeGridArray.length>0,r.currentProgram=d,r.uniformsList=null,d}function ct(e){if(e.uniformsList===null){let t=e.currentProgram.getUniforms();e.uniformsList=Sm.seqWithValue(t.seq,e.uniforms)}return e.uniformsList}function lt(e,t){let n=I.get(e);n.outputColorSpace=t.outputColorSpace,n.batching=t.batching,n.batchingColor=t.batchingColor,n.instancing=t.instancing,n.instancingColor=t.instancingColor,n.instancingMorph=t.instancingMorph,n.skinning=t.skinning,n.morphTargets=t.morphTargets,n.morphNormals=t.morphNormals,n.morphColors=t.morphColors,n.morphTargetsCount=t.morphTargetsCount,n.numClippingPlanes=t.numClippingPlanes,n.numIntersection=t.numClipIntersection,n.vertexAlphas=t.vertexAlphas,n.vertexTangents=t.vertexTangents,n.toneMapping=t.toneMapping}function ut(e,t){if(e.length===0)return null;if(e.length===1)return e[0].texture===null?null:e[0];y.setFromMatrixPosition(t.matrixWorld);for(let t=0,n=e.length;t<n;t++){let n=e[t];if(n.texture!==null&&n.boundingBox.containsPoint(y))return n}return null}function dt(e,t,n,r,i){t.isScene!==!0&&(t=ve),L.resetTextureUnits();let a=t.fog,o=r.isMeshStandardMaterial||r.isMeshLambertMaterial||r.isMeshPhongMaterial?t.environment:null,s=A===null?T.outputColorSpace:A.isXRRenderTarget===!0?A.texture.colorSpace:Xo.workingColorSpace,c=r.isMeshStandardMaterial||r.isMeshLambertMaterial&&!r.envMap||r.isMeshPhongMaterial&&!r.envMap,l=Te.get(r.envMap||o,c),u=r.vertexColors===!0&&!!n.attributes.color&&n.attributes.color.itemSize===4,d=!!n.attributes.tangent&&(!!r.normalMap||r.anisotropy>0),f=!!n.morphAttributes.position,p=!!n.morphAttributes.normal,m=!!n.morphAttributes.color,h=0;r.toneMapped&&(A===null||A.isXRRenderTarget===!0)&&(h=T.toneMapping);let g=n.morphAttributes.position||n.morphAttributes.normal||n.morphAttributes.color,_=g===void 0?0:g.length,v=I.get(r),y=x.state.lights;if(pe===!0&&(me===!0||e!==te)){let t=e===te&&r.id===ee;Ne.setState(r,e,t)}let b=!1;r.version===v.__version?v.needsLights&&v.lightsStateVersion!==y.state.version?b=!0:v.outputColorSpace===s?i.isBatchedMesh&&v.batching===!1||!i.isBatchedMesh&&v.batching===!0||i.isBatchedMesh&&v.batchingColor===!0&&i.colorTexture===null||i.isBatchedMesh&&v.batchingColor===!1&&i.colorTexture!==null||i.isInstancedMesh&&v.instancing===!1||!i.isInstancedMesh&&v.instancing===!0||i.isSkinnedMesh&&v.skinning===!1||!i.isSkinnedMesh&&v.skinning===!0||i.isInstancedMesh&&v.instancingColor===!0&&i.instanceColor===null||i.isInstancedMesh&&v.instancingColor===!1&&i.instanceColor!==null||i.isInstancedMesh&&v.instancingMorph===!0&&i.morphTexture===null||i.isInstancedMesh&&v.instancingMorph===!1&&i.morphTexture!==null?b=!0:v.envMap===l?r.fog===!0&&v.fog!==a||v.numClippingPlanes!==void 0&&(v.numClippingPlanes!==Ne.numPlanes||v.numIntersection!==Ne.numIntersection)?b=!0:v.vertexAlphas===u&&v.vertexTangents===d&&v.morphTargets===f&&v.morphNormals===p&&v.morphColors===m&&v.toneMapping===h&&v.morphTargetsCount===_?!!v.lightProbeGrid!=x.state.lightProbeGridArray.length>0&&(b=!0):b=!0:b=!0:b=!0:(b=!0,v.__version=r.version);let S=v.currentProgram;b===!0&&(S=st(r,t,i),D&&r.isNodeMaterial&&D.onUpdateProgram(r,S,v));let C=!1,w=!1,E=!1,O=S.getUniforms(),k=v.uniforms;if(F.useProgram(S.program)&&(C=!0,w=!0,E=!0),r.id!==ee&&(ee=r.id,w=!0),v.needsLights){let e=ut(x.state.lightProbeGridArray,i);v.lightProbeGrid!==e&&(v.lightProbeGrid=e,w=!0)}if(C||te!==e){F.buffers.depth.getReversed()&&e.reversedDepth!==!0&&(e._reversedDepth=!0,e.updateProjectionMatrix()),O.setValue(P,`projectionMatrix`,e.projectionMatrix),O.setValue(P,`viewMatrix`,e.matrixWorldInverse);let t=O.map.cameraPosition;t!==void 0&&t.setValue(P,ge.setFromMatrixPosition(e.matrixWorld)),Ce.logarithmicDepthBuffer&&O.setValue(P,`logDepthBufFC`,2/(Math.log(e.far+1)/Math.LN2)),(r.isMeshPhongMaterial||r.isMeshToonMaterial||r.isMeshLambertMaterial||r.isMeshBasicMaterial||r.isMeshStandardMaterial||r.isShaderMaterial)&&O.setValue(P,`isOrthographic`,e.isOrthographicCamera===!0),te!==e&&(te=e,w=!0,E=!0)}if(v.needsLights&&(y.state.directionalShadowMap.length>0&&O.setValue(P,`directionalShadowMap`,y.state.directionalShadowMap,L),y.state.spotShadowMap.length>0&&O.setValue(P,`spotShadowMap`,y.state.spotShadowMap,L),y.state.pointShadowMap.length>0&&O.setValue(P,`pointShadowMap`,y.state.pointShadowMap,L)),i.isSkinnedMesh){O.setOptional(P,i,`bindMatrix`),O.setOptional(P,i,`bindMatrixInverse`);let e=i.skeleton;e&&(e.boneTexture===null&&e.computeBoneTexture(),O.setValue(P,`boneTexture`,e.boneTexture,L))}i.isBatchedMesh&&(O.setOptional(P,i,`batchingTexture`),O.setValue(P,`batchingTexture`,i._matricesTexture,L),O.setOptional(P,i,`batchingIdTexture`),O.setValue(P,`batchingIdTexture`,i._indirectTexture,L),O.setOptional(P,i,`batchingColorTexture`),i._colorsTexture!==null&&O.setValue(P,`batchingColorTexture`,i._colorsTexture,L));let j=n.morphAttributes;if((j.position!==void 0||j.normal!==void 0||j.color!==void 0)&&Ie.update(i,n,S),(w||v.receiveShadow!==i.receiveShadow)&&(v.receiveShadow=i.receiveShadow,O.setValue(P,`receiveShadow`,i.receiveShadow)),(r.isMeshStandardMaterial||r.isMeshLambertMaterial||r.isMeshPhongMaterial)&&r.envMap===null&&t.environment!==null&&(k.envMapIntensity.value=t.environmentIntensity),k.dfgLUT!==void 0&&(k.dfgLUT.value=Uh()),w){if(O.setValue(P,`toneMappingExposure`,T.toneMappingExposure),v.needsLights&&ft(k,E),a&&r.fog===!0&&Ae.refreshFogUniforms(k,a),Ae.refreshMaterialUniforms(k,r,oe,ae,x.state.transmissionRenderTarget[e.id]),v.needsLights&&v.lightProbeGrid){let e=v.lightProbeGrid;k.probesSH.value=e.texture,k.probesMin.value.copy(e.boundingBox.min),k.probesMax.value.copy(e.boundingBox.max),k.probesResolution.value.copy(e.resolution)}Sm.upload(P,ct(v),k,L)}if(r.isShaderMaterial&&r.uniformsNeedUpdate===!0&&(Sm.upload(P,ct(v),k,L),r.uniformsNeedUpdate=!1),r.isSpriteMaterial&&O.setValue(P,`center`,i.center),O.setValue(P,`modelViewMatrix`,i.modelViewMatrix),O.setValue(P,`normalMatrix`,i.normalMatrix),O.setValue(P,`modelMatrix`,i.matrixWorld),r.uniformsGroups!==void 0){let e=r.uniformsGroups;for(let t=0,n=e.length;t<n;t++){let n=e[t];Ve.update(n,S),Ve.bind(n,S)}}return S}function ft(e,t){e.ambientLightColor.needsUpdate=t,e.lightProbe.needsUpdate=t,e.directionalLights.needsUpdate=t,e.directionalLightShadows.needsUpdate=t,e.pointLights.needsUpdate=t,e.pointLightShadows.needsUpdate=t,e.spotLights.needsUpdate=t,e.spotLightShadows.needsUpdate=t,e.rectAreaLights.needsUpdate=t,e.hemisphereLights.needsUpdate=t}function pt(e){return e.isMeshLambertMaterial||e.isMeshToonMaterial||e.isMeshPhongMaterial||e.isMeshStandardMaterial||e.isShadowMaterial||e.isShaderMaterial&&e.lights===!0}this.getActiveCubeFace=function(){return O},this.getActiveMipmapLevel=function(){return k},this.getRenderTarget=function(){return A},this.setRenderTargetTextures=function(e,t,n){let r=I.get(e);r.__autoAllocateDepthBuffer=e.resolveDepthBuffer===!1,r.__autoAllocateDepthBuffer===!1&&(r.__useRenderToTexture=!1),I.get(e.texture).__webglTexture=t,I.get(e.depthTexture).__webglTexture=r.__autoAllocateDepthBuffer?void 0:n,r.__hasExternalTextures=!0},this.setRenderTargetFramebuffer=function(e,t){let n=I.get(e);n.__webglFramebuffer=t,n.__useDefaultFramebuffer=t===void 0};let mt=P.createFramebuffer();this.setRenderTarget=function(e,t=0,n=0){A=e,O=t,k=n;let r=null,i=!1,a=!1;if(e){let o=I.get(e);if(o.__useDefaultFramebuffer!==void 0){F.bindFramebuffer(P.FRAMEBUFFER,o.__webglFramebuffer),j.copy(e.viewport),ne.copy(e.scissor),M=e.scissorTest,F.viewport(j),F.scissor(ne),F.setScissorTest(M),ee=-1;return}else if(o.__webglFramebuffer===void 0)L.setupRenderTarget(e);else if(o.__hasExternalTextures)L.rebindTextures(e,I.get(e.texture).__webglTexture,I.get(e.depthTexture).__webglTexture);else if(e.depthBuffer){let t=e.depthTexture;if(o.__boundDepthTexture!==t){if(t!==null&&I.has(t)&&(e.width!==t.image.width||e.height!==t.image.height))throw Error(`WebGLRenderTarget: Attached DepthTexture is initialized to the incorrect size.`);L.setupDepthRenderbuffer(e)}}let s=e.texture;(s.isData3DTexture||s.isDataArrayTexture||s.isCompressedArrayTexture)&&(a=!0);let c=I.get(e).__webglFramebuffer;e.isWebGLCubeRenderTarget?(r=Array.isArray(c[t])?c[t][n]:c[t],i=!0):r=e.samples>0&&L.useMultisampledRTT(e)===!1?I.get(e).__webglMultisampledFramebuffer:Array.isArray(c)?c[n]:c,j.copy(e.viewport),ne.copy(e.scissor),M=e.scissorTest}else j.copy(le).multiplyScalar(oe).floor(),ne.copy(ue).multiplyScalar(oe).floor(),M=de;if(n!==0&&(r=mt),F.bindFramebuffer(P.FRAMEBUFFER,r)&&F.drawBuffers(e,r),F.viewport(j),F.scissor(ne),F.setScissorTest(M),i){let r=I.get(e.texture);P.framebufferTexture2D(P.FRAMEBUFFER,P.COLOR_ATTACHMENT0,P.TEXTURE_CUBE_MAP_POSITIVE_X+t,r.__webglTexture,n)}else if(a){let r=t;for(let t=0;t<e.textures.length;t++){let i=I.get(e.textures[t]);P.framebufferTextureLayer(P.FRAMEBUFFER,P.COLOR_ATTACHMENT0+t,i.__webglTexture,n,r)}}else if(e!==null&&n!==0){let t=I.get(e.texture);P.framebufferTexture2D(P.FRAMEBUFFER,P.COLOR_ATTACHMENT0,P.TEXTURE_2D,t.__webglTexture,n)}ee=-1},this.readRenderTargetPixels=function(e,t,n,r,i,a,o,s=0){if(!(e&&e.isWebGLRenderTarget)){z(`WebGLRenderer.readRenderTargetPixels: renderTarget is not THREE.WebGLRenderTarget.`);return}let c=I.get(e).__webglFramebuffer;if(e.isWebGLCubeRenderTarget&&o!==void 0&&(c=c[o]),c){F.bindFramebuffer(P.FRAMEBUFFER,c);try{let o=e.textures[s],c=o.format,l=o.type;if(e.textures.length>1&&P.readBuffer(P.COLOR_ATTACHMENT0+s),!Ce.textureFormatReadable(c)){z(`WebGLRenderer.readRenderTargetPixels: renderTarget is not in RGBA or implementation defined format.`);return}if(!Ce.textureTypeReadable(l)){z(`WebGLRenderer.readRenderTargetPixels: renderTarget is not in UnsignedByteType or implementation defined type.`);return}t>=0&&t<=e.width-r&&n>=0&&n<=e.height-i&&P.readPixels(t,n,r,i,ze.convert(c),ze.convert(l),a)}finally{let e=A===null?null:I.get(A).__webglFramebuffer;F.bindFramebuffer(P.FRAMEBUFFER,e)}}},this.readRenderTargetPixelsAsync=async function(e,t,n,r,i,a,o,s=0){if(!(e&&e.isWebGLRenderTarget))throw Error(`THREE.WebGLRenderer.readRenderTargetPixels: renderTarget is not THREE.WebGLRenderTarget.`);let c=I.get(e).__webglFramebuffer;if(e.isWebGLCubeRenderTarget&&o!==void 0&&(c=c[o]),c)if(t>=0&&t<=e.width-r&&n>=0&&n<=e.height-i){F.bindFramebuffer(P.FRAMEBUFFER,c);let o=e.textures[s],l=o.format,u=o.type;if(e.textures.length>1&&P.readBuffer(P.COLOR_ATTACHMENT0+s),!Ce.textureFormatReadable(l))throw Error(`THREE.WebGLRenderer.readRenderTargetPixelsAsync: renderTarget is not in RGBA or implementation defined format.`);if(!Ce.textureTypeReadable(u))throw Error(`THREE.WebGLRenderer.readRenderTargetPixelsAsync: renderTarget is not in UnsignedByteType or implementation defined type.`);let d=P.createBuffer();P.bindBuffer(P.PIXEL_PACK_BUFFER,d),P.bufferData(P.PIXEL_PACK_BUFFER,a.byteLength,P.STREAM_READ),P.readPixels(t,n,r,i,ze.convert(l),ze.convert(u),0);let f=A===null?null:I.get(A).__webglFramebuffer;F.bindFramebuffer(P.FRAMEBUFFER,f);let p=P.fenceSync(P.SYNC_GPU_COMMANDS_COMPLETE,0);return P.flush(),await mo(P,p,4),P.bindBuffer(P.PIXEL_PACK_BUFFER,d),P.getBufferSubData(P.PIXEL_PACK_BUFFER,0,a),P.deleteBuffer(d),P.deleteSync(p),a}else throw Error(`THREE.WebGLRenderer.readRenderTargetPixelsAsync: requested read bounds are out of range.`)},this.copyFramebufferToTexture=function(e,t=null,n=0){let r=2**-n,i=Math.floor(e.image.width*r),a=Math.floor(e.image.height*r),o=t===null?0:t.x,s=t===null?0:t.y;L.setTexture2D(e,0),P.copyTexSubImage2D(P.TEXTURE_2D,n,0,0,o,s,i,a),F.unbindTexture()};let ht=P.createFramebuffer(),gt=P.createFramebuffer();this.copyTextureToTexture=function(e,t,n=null,r=null,i=0,a=0){let o,s,c,l,u,d,f,p,m,h=e.isCompressedTexture?e.mipmaps[a]:e.image;if(n!==null)o=n.max.x-n.min.x,s=n.max.y-n.min.y,c=n.isBox3?n.max.z-n.min.z:1,l=n.min.x,u=n.min.y,d=n.isBox3?n.min.z:0;else{let t=2**-i;o=Math.floor(h.width*t),s=Math.floor(h.height*t),c=e.isDataArrayTexture?h.depth:e.isData3DTexture?Math.floor(h.depth*t):1,l=0,u=0,d=0}r===null?(f=0,p=0,m=0):(f=r.x,p=r.y,m=r.z);let g=ze.convert(t.format),_=ze.convert(t.type),v;t.isData3DTexture?(L.setTexture3D(t,0),v=P.TEXTURE_3D):t.isDataArrayTexture||t.isCompressedArrayTexture?(L.setTexture2DArray(t,0),v=P.TEXTURE_2D_ARRAY):(L.setTexture2D(t,0),v=P.TEXTURE_2D),F.activeTexture(P.TEXTURE0),F.pixelStorei(P.UNPACK_FLIP_Y_WEBGL,t.flipY),F.pixelStorei(P.UNPACK_PREMULTIPLY_ALPHA_WEBGL,t.premultiplyAlpha),F.pixelStorei(P.UNPACK_ALIGNMENT,t.unpackAlignment);let y=F.getParameter(P.UNPACK_ROW_LENGTH),b=F.getParameter(P.UNPACK_IMAGE_HEIGHT),x=F.getParameter(P.UNPACK_SKIP_PIXELS),S=F.getParameter(P.UNPACK_SKIP_ROWS),C=F.getParameter(P.UNPACK_SKIP_IMAGES);F.pixelStorei(P.UNPACK_ROW_LENGTH,h.width),F.pixelStorei(P.UNPACK_IMAGE_HEIGHT,h.height),F.pixelStorei(P.UNPACK_SKIP_PIXELS,l),F.pixelStorei(P.UNPACK_SKIP_ROWS,u),F.pixelStorei(P.UNPACK_SKIP_IMAGES,d);let w=e.isDataArrayTexture||e.isData3DTexture,T=t.isDataArrayTexture||t.isData3DTexture;if(e.isDepthTexture){let n=I.get(e),r=I.get(t),h=I.get(n.__renderTarget),g=I.get(r.__renderTarget);F.bindFramebuffer(P.READ_FRAMEBUFFER,h.__webglFramebuffer),F.bindFramebuffer(P.DRAW_FRAMEBUFFER,g.__webglFramebuffer);for(let n=0;n<c;n++)w&&(P.framebufferTextureLayer(P.READ_FRAMEBUFFER,P.COLOR_ATTACHMENT0,I.get(e).__webglTexture,i,d+n),P.framebufferTextureLayer(P.DRAW_FRAMEBUFFER,P.COLOR_ATTACHMENT0,I.get(t).__webglTexture,a,m+n)),P.blitFramebuffer(l,u,o,s,f,p,o,s,P.DEPTH_BUFFER_BIT,P.NEAREST);F.bindFramebuffer(P.READ_FRAMEBUFFER,null),F.bindFramebuffer(P.DRAW_FRAMEBUFFER,null)}else if(i!==0||e.isRenderTargetTexture||I.has(e)){let n=I.get(e),r=I.get(t);F.bindFramebuffer(P.READ_FRAMEBUFFER,ht),F.bindFramebuffer(P.DRAW_FRAMEBUFFER,gt);for(let e=0;e<c;e++)w?P.framebufferTextureLayer(P.READ_FRAMEBUFFER,P.COLOR_ATTACHMENT0,n.__webglTexture,i,d+e):P.framebufferTexture2D(P.READ_FRAMEBUFFER,P.COLOR_ATTACHMENT0,P.TEXTURE_2D,n.__webglTexture,i),T?P.framebufferTextureLayer(P.DRAW_FRAMEBUFFER,P.COLOR_ATTACHMENT0,r.__webglTexture,a,m+e):P.framebufferTexture2D(P.DRAW_FRAMEBUFFER,P.COLOR_ATTACHMENT0,P.TEXTURE_2D,r.__webglTexture,a),i===0?T?P.copyTexSubImage3D(v,a,f,p,m+e,l,u,o,s):P.copyTexSubImage2D(v,a,f,p,l,u,o,s):P.blitFramebuffer(l,u,o,s,f,p,o,s,P.COLOR_BUFFER_BIT,P.NEAREST);F.bindFramebuffer(P.READ_FRAMEBUFFER,null),F.bindFramebuffer(P.DRAW_FRAMEBUFFER,null)}else T?e.isDataTexture||e.isData3DTexture?P.texSubImage3D(v,a,f,p,m,o,s,c,g,_,h.data):t.isCompressedArrayTexture?P.compressedTexSubImage3D(v,a,f,p,m,o,s,c,g,h.data):P.texSubImage3D(v,a,f,p,m,o,s,c,g,_,h):e.isDataTexture?P.texSubImage2D(P.TEXTURE_2D,a,f,p,o,s,g,_,h.data):e.isCompressedTexture?P.compressedTexSubImage2D(P.TEXTURE_2D,a,f,p,h.width,h.height,g,h.data):P.texSubImage2D(P.TEXTURE_2D,a,f,p,o,s,g,_,h);F.pixelStorei(P.UNPACK_ROW_LENGTH,y),F.pixelStorei(P.UNPACK_IMAGE_HEIGHT,b),F.pixelStorei(P.UNPACK_SKIP_PIXELS,x),F.pixelStorei(P.UNPACK_SKIP_ROWS,S),F.pixelStorei(P.UNPACK_SKIP_IMAGES,C),a===0&&t.generateMipmaps&&P.generateMipmap(v),F.unbindTexture()},this.initRenderTarget=function(e){I.get(e).__webglFramebuffer===void 0&&L.setupRenderTarget(e)},this.initTexture=function(e){e.isCubeTexture?L.setTextureCube(e,0):e.isData3DTexture?L.setTexture3D(e,0):e.isDataArrayTexture||e.isCompressedArrayTexture?L.setTexture2DArray(e,0):L.setTexture2D(e,0),F.unbindTexture()},this.resetState=function(){O=0,k=0,A=null,F.reset(),Be.reset()},typeof __THREE_DEVTOOLS__<`u`&&__THREE_DEVTOOLS__.dispatchEvent(new CustomEvent(`observe`,{detail:this}))}get coordinateSystem(){return ro}get outputColorSpace(){return this._outputColorSpace}set outputColorSpace(e){this._outputColorSpace=e;let t=this.getContext();t.drawingBufferColorSpace=Xo._getDrawingBufferColorSpace(e),t.unpackColorSpace=Xo._getUnpackColorSpace()}},Gh={type:`change`},Kh={type:`start`},qh={type:`end`},Jh=new gl,Yh=new Gl,Xh=Math.cos(70*Ho.DEG2RAD),Zh=new H,Qh=2*Math.PI,$h={NONE:-1,ROTATE:0,DOLLY:1,PAN:2,TOUCH_ROTATE:3,TOUCH_PAN:4,TOUCH_DOLLY_PAN:5,TOUCH_DOLLY_ROTATE:6},eg=1e-6,tg=class extends Ef{constructor(e,t=null){super(e,t),this.state=$h.NONE,this.target=new H,this.cursor=new H,this.minDistance=0,this.maxDistance=1/0,this.minZoom=0,this.maxZoom=1/0,this.minTargetRadius=0,this.maxTargetRadius=1/0,this.minPolarAngle=0,this.maxPolarAngle=Math.PI,this.minAzimuthAngle=-1/0,this.maxAzimuthAngle=1/0,this.enableDamping=!1,this.dampingFactor=.05,this.enableZoom=!0,this.zoomSpeed=1,this.enableRotate=!0,this.rotateSpeed=1,this.keyRotateSpeed=1,this.enablePan=!0,this.panSpeed=1,this.screenSpacePanning=!0,this.keyPanSpeed=7,this.zoomToCursor=!1,this.autoRotate=!1,this.autoRotateSpeed=2,this.keys={LEFT:`ArrowLeft`,UP:`ArrowUp`,RIGHT:`ArrowRight`,BOTTOM:`ArrowDown`},this.mouseButtons={LEFT:Ei.ROTATE,MIDDLE:Ei.DOLLY,RIGHT:Ei.PAN},this.touches={ONE:Di.ROTATE,TWO:Di.DOLLY_PAN},this.target0=this.target.clone(),this.position0=this.object.position.clone(),this.zoom0=this.object.zoom,this._cursorStyle=`auto`,this._domElementKeyEvents=null,this._lastPosition=new H,this._lastQuaternion=new Uo,this._lastTargetPosition=new H,this._quat=new Uo().setFromUnitVectors(e.up,new H(0,1,0)),this._quatInverse=this._quat.clone().invert(),this._spherical=new vf,this._sphericalDelta=new vf,this._scale=1,this._panOffset=new H,this._rotateStart=new V,this._rotateEnd=new V,this._rotateDelta=new V,this._panStart=new V,this._panEnd=new V,this._panDelta=new V,this._dollyStart=new V,this._dollyEnd=new V,this._dollyDelta=new V,this._dollyDirection=new H,this._mouse=new V,this._performCursorZoom=!1,this._pointers=[],this._pointerPositions={},this._controlActive=!1,this._onPointerMove=rg.bind(this),this._onPointerDown=ng.bind(this),this._onPointerUp=ig.bind(this),this._onContextMenu=dg.bind(this),this._onMouseWheel=sg.bind(this),this._onKeyDown=cg.bind(this),this._onTouchStart=lg.bind(this),this._onTouchMove=ug.bind(this),this._onMouseDown=ag.bind(this),this._onMouseMove=og.bind(this),this._interceptControlDown=fg.bind(this),this._interceptControlUp=pg.bind(this),this.domElement!==null&&this.connect(this.domElement),this.update()}set cursorStyle(e){this._cursorStyle=e,e===`grab`?this.domElement.style.cursor=`grab`:this.domElement.style.cursor=`auto`}get cursorStyle(){return this._cursorStyle}connect(e){super.connect(e),this.domElement.addEventListener(`pointerdown`,this._onPointerDown),this.domElement.addEventListener(`pointercancel`,this._onPointerUp),this.domElement.addEventListener(`contextmenu`,this._onContextMenu),this.domElement.addEventListener(`wheel`,this._onMouseWheel,{passive:!1}),this.domElement.getRootNode().addEventListener(`keydown`,this._interceptControlDown,{passive:!0,capture:!0}),this.domElement.style.touchAction=`none`}disconnect(){this.domElement.removeEventListener(`pointerdown`,this._onPointerDown),this.domElement.ownerDocument.removeEventListener(`pointermove`,this._onPointerMove),this.domElement.ownerDocument.removeEventListener(`pointerup`,this._onPointerUp),this.domElement.removeEventListener(`pointercancel`,this._onPointerUp),this.domElement.removeEventListener(`wheel`,this._onMouseWheel),this.domElement.removeEventListener(`contextmenu`,this._onContextMenu),this.stopListenToKeyEvents(),this.domElement.getRootNode().removeEventListener(`keydown`,this._interceptControlDown,{capture:!0}),this.domElement.style.touchAction=``}dispose(){this.disconnect()}getPolarAngle(){return this._spherical.phi}getAzimuthalAngle(){return this._spherical.theta}getDistance(){return this.object.position.distanceTo(this.target)}listenToKeyEvents(e){e.addEventListener(`keydown`,this._onKeyDown),this._domElementKeyEvents=e}stopListenToKeyEvents(){this._domElementKeyEvents!==null&&(this._domElementKeyEvents.removeEventListener(`keydown`,this._onKeyDown),this._domElementKeyEvents=null)}saveState(){this.target0.copy(this.target),this.position0.copy(this.object.position),this.zoom0=this.object.zoom}reset(){this.target.copy(this.target0),this.object.position.copy(this.position0),this.object.zoom=this.zoom0,this.object.updateProjectionMatrix(),this.dispatchEvent(Gh),this.update(),this.state=$h.NONE}pan(e,t){this._pan(e,t),this.update()}dollyIn(e){this._dollyIn(e),this.update()}dollyOut(e){this._dollyOut(e),this.update()}rotateLeft(e){this._rotateLeft(e),this.update()}rotateUp(e){this._rotateUp(e),this.update()}update(e=null){let t=this.object.position;Zh.copy(t).sub(this.target),Zh.applyQuaternion(this._quat),this._spherical.setFromVector3(Zh),this.autoRotate&&this.state===$h.NONE&&this._rotateLeft(this._getAutoRotationAngle(e)),this.enableDamping?(this._spherical.theta+=this._sphericalDelta.theta*this.dampingFactor,this._spherical.phi+=this._sphericalDelta.phi*this.dampingFactor):(this._spherical.theta+=this._sphericalDelta.theta,this._spherical.phi+=this._sphericalDelta.phi);let n=this.minAzimuthAngle,r=this.maxAzimuthAngle;isFinite(n)&&isFinite(r)&&(n<-Math.PI?n+=Qh:n>Math.PI&&(n-=Qh),r<-Math.PI?r+=Qh:r>Math.PI&&(r-=Qh),n<=r?this._spherical.theta=Math.max(n,Math.min(r,this._spherical.theta)):this._spherical.theta=this._spherical.theta>(n+r)/2?Math.max(n,this._spherical.theta):Math.min(r,this._spherical.theta)),this._spherical.phi=Math.max(this.minPolarAngle,Math.min(this.maxPolarAngle,this._spherical.phi)),this._spherical.makeSafe(),this.enableDamping===!0?this.target.addScaledVector(this._panOffset,this.dampingFactor):this.target.add(this._panOffset),this.target.sub(this.cursor),this.target.clampLength(this.minTargetRadius,this.maxTargetRadius),this.target.add(this.cursor);let i=!1;if(this.zoomToCursor&&this._performCursorZoom||this.object.isOrthographicCamera)this._spherical.radius=this._clampDistance(this._spherical.radius);else{let e=this._spherical.radius;this._spherical.radius=this._clampDistance(this._spherical.radius*this._scale),i=e!=this._spherical.radius}if(Zh.setFromSpherical(this._spherical),Zh.applyQuaternion(this._quatInverse),t.copy(this.target).add(Zh),this.object.lookAt(this.target),this.enableDamping===!0?(this._sphericalDelta.theta*=1-this.dampingFactor,this._sphericalDelta.phi*=1-this.dampingFactor,this._panOffset.multiplyScalar(1-this.dampingFactor)):(this._sphericalDelta.set(0,0,0),this._panOffset.set(0,0,0)),this.zoomToCursor&&this._performCursorZoom){let e=null;if(this.object.isPerspectiveCamera){let t=Zh.length();e=this._clampDistance(t*this._scale);let n=t-e;this.object.position.addScaledVector(this._dollyDirection,n),this.object.updateMatrixWorld(),i=!!n}else if(this.object.isOrthographicCamera){let t=new H(this._mouse.x,this._mouse.y,0);t.unproject(this.object);let n=this.object.zoom;this.object.zoom=Math.max(this.minZoom,Math.min(this.maxZoom,this.object.zoom/this._scale)),this.object.updateProjectionMatrix(),i=n!==this.object.zoom;let r=new H(this._mouse.x,this._mouse.y,0);r.unproject(this.object),this.object.position.sub(r).add(t),this.object.updateMatrixWorld(),e=Zh.length()}else console.warn(`WARNING: OrbitControls.js encountered an unknown camera type - zoom to cursor disabled.`),this.zoomToCursor=!1;e!==null&&(this.screenSpacePanning?this.target.set(0,0,-1).transformDirection(this.object.matrix).multiplyScalar(e).add(this.object.position):(Jh.origin.copy(this.object.position),Jh.direction.set(0,0,-1).transformDirection(this.object.matrix),Math.abs(this.object.up.dot(Jh.direction))<Xh?this.object.lookAt(this.target):(Yh.setFromNormalAndCoplanarPoint(this.object.up,this.target),Jh.intersectPlane(Yh,this.target))))}else if(this.object.isOrthographicCamera){let e=this.object.zoom;this.object.zoom=Math.max(this.minZoom,Math.min(this.maxZoom,this.object.zoom/this._scale)),e!==this.object.zoom&&(this.object.updateProjectionMatrix(),i=!0)}return this._scale=1,this._performCursorZoom=!1,i||this._lastPosition.distanceToSquared(this.object.position)>eg||8*(1-this._lastQuaternion.dot(this.object.quaternion))>eg||this._lastTargetPosition.distanceToSquared(this.target)>eg?(this.dispatchEvent(Gh),this._lastPosition.copy(this.object.position),this._lastQuaternion.copy(this.object.quaternion),this._lastTargetPosition.copy(this.target),!0):!1}_getAutoRotationAngle(e){return e===null?Qh/60/60*this.autoRotateSpeed:Qh/60*this.autoRotateSpeed*e}_getZoomScale(e){let t=Math.abs(e*.01);return .95**(this.zoomSpeed*t)}_rotateLeft(e){this._sphericalDelta.theta-=e}_rotateUp(e){this._sphericalDelta.phi-=e}_panLeft(e,t){Zh.setFromMatrixColumn(t,0),Zh.multiplyScalar(-e),this._panOffset.add(Zh)}_panUp(e,t){this.screenSpacePanning===!0?Zh.setFromMatrixColumn(t,1):(Zh.setFromMatrixColumn(t,0),Zh.crossVectors(this.object.up,Zh)),Zh.multiplyScalar(e),this._panOffset.add(Zh)}_pan(e,t){let n=this.domElement;if(this.object.isPerspectiveCamera){let r=this.object.position;Zh.copy(r).sub(this.target);let i=Zh.length();i*=Math.tan(this.object.fov/2*Math.PI/180),this._panLeft(2*e*i/n.clientHeight,this.object.matrix),this._panUp(2*t*i/n.clientHeight,this.object.matrix)}else this.object.isOrthographicCamera?(this._panLeft(e*(this.object.right-this.object.left)/this.object.zoom/n.clientWidth,this.object.matrix),this._panUp(t*(this.object.top-this.object.bottom)/this.object.zoom/n.clientHeight,this.object.matrix)):(console.warn(`WARNING: OrbitControls.js encountered an unknown camera type - pan disabled.`),this.enablePan=!1)}_dollyOut(e){this.object.isPerspectiveCamera||this.object.isOrthographicCamera?this._scale/=e:(console.warn(`WARNING: OrbitControls.js encountered an unknown camera type - dolly/zoom disabled.`),this.enableZoom=!1)}_dollyIn(e){this.object.isPerspectiveCamera||this.object.isOrthographicCamera?this._scale*=e:(console.warn(`WARNING: OrbitControls.js encountered an unknown camera type - dolly/zoom disabled.`),this.enableZoom=!1)}_updateZoomParameters(e,t){if(!this.zoomToCursor)return;this._performCursorZoom=!0;let n=this.domElement.getBoundingClientRect(),r=e-n.left,i=t-n.top,a=n.width,o=n.height;this._mouse.x=r/a*2-1,this._mouse.y=-(i/o)*2+1,this._dollyDirection.set(this._mouse.x,this._mouse.y,1).unproject(this.object).sub(this.object.position).normalize()}_clampDistance(e){return Math.max(this.minDistance,Math.min(this.maxDistance,e))}_handleMouseDownRotate(e){this._rotateStart.set(e.clientX,e.clientY)}_handleMouseDownDolly(e){this._updateZoomParameters(e.clientX,e.clientX),this._dollyStart.set(e.clientX,e.clientY)}_handleMouseDownPan(e){this._panStart.set(e.clientX,e.clientY)}_handleMouseMoveRotate(e){this._rotateEnd.set(e.clientX,e.clientY),this._rotateDelta.subVectors(this._rotateEnd,this._rotateStart).multiplyScalar(this.rotateSpeed);let t=this.domElement;this._rotateLeft(Qh*this._rotateDelta.x/t.clientHeight),this._rotateUp(Qh*this._rotateDelta.y/t.clientHeight),this._rotateStart.copy(this._rotateEnd),this.update()}_handleMouseMoveDolly(e){this._dollyEnd.set(e.clientX,e.clientY),this._dollyDelta.subVectors(this._dollyEnd,this._dollyStart),this._dollyDelta.y>0?this._dollyOut(this._getZoomScale(this._dollyDelta.y)):this._dollyDelta.y<0&&this._dollyIn(this._getZoomScale(this._dollyDelta.y)),this._dollyStart.copy(this._dollyEnd),this.update()}_handleMouseMovePan(e){this._panEnd.set(e.clientX,e.clientY),this._panDelta.subVectors(this._panEnd,this._panStart).multiplyScalar(this.panSpeed),this._pan(this._panDelta.x,this._panDelta.y),this._panStart.copy(this._panEnd),this.update()}_handleMouseWheel(e){this._updateZoomParameters(e.clientX,e.clientY),e.deltaY<0?this._dollyIn(this._getZoomScale(e.deltaY)):e.deltaY>0&&this._dollyOut(this._getZoomScale(e.deltaY)),this.update()}_handleKeyDown(e){let t=!1;switch(e.code){case this.keys.UP:e.ctrlKey||e.metaKey||e.shiftKey?this.enableRotate&&this._rotateUp(Qh*this.keyRotateSpeed/this.domElement.clientHeight):this.enablePan&&this._pan(0,this.keyPanSpeed),t=!0;break;case this.keys.BOTTOM:e.ctrlKey||e.metaKey||e.shiftKey?this.enableRotate&&this._rotateUp(-Qh*this.keyRotateSpeed/this.domElement.clientHeight):this.enablePan&&this._pan(0,-this.keyPanSpeed),t=!0;break;case this.keys.LEFT:e.ctrlKey||e.metaKey||e.shiftKey?this.enableRotate&&this._rotateLeft(Qh*this.keyRotateSpeed/this.domElement.clientHeight):this.enablePan&&this._pan(this.keyPanSpeed,0),t=!0;break;case this.keys.RIGHT:e.ctrlKey||e.metaKey||e.shiftKey?this.enableRotate&&this._rotateLeft(-Qh*this.keyRotateSpeed/this.domElement.clientHeight):this.enablePan&&this._pan(-this.keyPanSpeed,0),t=!0;break}t&&(e.preventDefault(),this.update())}_handleTouchStartRotate(e){if(this._pointers.length===1)this._rotateStart.set(e.pageX,e.pageY);else{let t=this._getSecondPointerPosition(e),n=.5*(e.pageX+t.x),r=.5*(e.pageY+t.y);this._rotateStart.set(n,r)}}_handleTouchStartPan(e){if(this._pointers.length===1)this._panStart.set(e.pageX,e.pageY);else{let t=this._getSecondPointerPosition(e),n=.5*(e.pageX+t.x),r=.5*(e.pageY+t.y);this._panStart.set(n,r)}}_handleTouchStartDolly(e){let t=this._getSecondPointerPosition(e),n=e.pageX-t.x,r=e.pageY-t.y,i=Math.sqrt(n*n+r*r);this._dollyStart.set(0,i)}_handleTouchStartDollyPan(e){this.enableZoom&&this._handleTouchStartDolly(e),this.enablePan&&this._handleTouchStartPan(e)}_handleTouchStartDollyRotate(e){this.enableZoom&&this._handleTouchStartDolly(e),this.enableRotate&&this._handleTouchStartRotate(e)}_handleTouchMoveRotate(e){if(this._pointers.length==1)this._rotateEnd.set(e.pageX,e.pageY);else{let t=this._getSecondPointerPosition(e),n=.5*(e.pageX+t.x),r=.5*(e.pageY+t.y);this._rotateEnd.set(n,r)}this._rotateDelta.subVectors(this._rotateEnd,this._rotateStart).multiplyScalar(this.rotateSpeed);let t=this.domElement;this._rotateLeft(Qh*this._rotateDelta.x/t.clientHeight),this._rotateUp(Qh*this._rotateDelta.y/t.clientHeight),this._rotateStart.copy(this._rotateEnd)}_handleTouchMovePan(e){if(this._pointers.length===1)this._panEnd.set(e.pageX,e.pageY);else{let t=this._getSecondPointerPosition(e),n=.5*(e.pageX+t.x),r=.5*(e.pageY+t.y);this._panEnd.set(n,r)}this._panDelta.subVectors(this._panEnd,this._panStart).multiplyScalar(this.panSpeed),this._pan(this._panDelta.x,this._panDelta.y),this._panStart.copy(this._panEnd)}_handleTouchMoveDolly(e){let t=this._getSecondPointerPosition(e),n=e.pageX-t.x,r=e.pageY-t.y,i=Math.sqrt(n*n+r*r);this._dollyEnd.set(0,i),this._dollyDelta.set(0,(this._dollyEnd.y/this._dollyStart.y)**+this.zoomSpeed),this._dollyOut(this._dollyDelta.y),this._dollyStart.copy(this._dollyEnd);let a=(e.pageX+t.x)*.5,o=(e.pageY+t.y)*.5;this._updateZoomParameters(a,o)}_handleTouchMoveDollyPan(e){this.enableZoom&&this._handleTouchMoveDolly(e),this.enablePan&&this._handleTouchMovePan(e)}_handleTouchMoveDollyRotate(e){this.enableZoom&&this._handleTouchMoveDolly(e),this.enableRotate&&this._handleTouchMoveRotate(e)}_addPointer(e){this._pointers.push(e.pointerId)}_removePointer(e){delete this._pointerPositions[e.pointerId];for(let t=0;t<this._pointers.length;t++)if(this._pointers[t]==e.pointerId){this._pointers.splice(t,1);return}}_isTrackingPointer(e){for(let t=0;t<this._pointers.length;t++)if(this._pointers[t]==e.pointerId)return!0;return!1}_trackPointer(e){let t=this._pointerPositions[e.pointerId];t===void 0&&(t=new V,this._pointerPositions[e.pointerId]=t),t.set(e.pageX,e.pageY)}_getSecondPointerPosition(e){let t=e.pointerId===this._pointers[0]?this._pointers[1]:this._pointers[0];return this._pointerPositions[t]}_customWheelEvent(e){let t=e.deltaMode,n={clientX:e.clientX,clientY:e.clientY,deltaY:e.deltaY};switch(t){case 1:n.deltaY*=16;break;case 2:n.deltaY*=100;break}return e.ctrlKey&&!this._controlActive&&(n.deltaY*=10),n}};function ng(e){this.enabled!==!1&&(this._pointers.length===0&&(this.domElement.setPointerCapture(e.pointerId),this.domElement.ownerDocument.addEventListener(`pointermove`,this._onPointerMove),this.domElement.ownerDocument.addEventListener(`pointerup`,this._onPointerUp)),!this._isTrackingPointer(e)&&(this._addPointer(e),e.pointerType===`touch`?this._onTouchStart(e):this._onMouseDown(e),this._cursorStyle===`grab`&&(this.domElement.style.cursor=`grabbing`)))}function rg(e){this.enabled!==!1&&(e.pointerType===`touch`?this._onTouchMove(e):this._onMouseMove(e))}function ig(e){switch(this._removePointer(e),this._pointers.length){case 0:this.domElement.releasePointerCapture(e.pointerId),this.domElement.ownerDocument.removeEventListener(`pointermove`,this._onPointerMove),this.domElement.ownerDocument.removeEventListener(`pointerup`,this._onPointerUp),this.dispatchEvent(qh),this.state=$h.NONE,this._cursorStyle===`grab`&&(this.domElement.style.cursor=`grab`);break;case 1:let t=this._pointers[0],n=this._pointerPositions[t];this._onTouchStart({pointerId:t,pageX:n.x,pageY:n.y});break}}function ag(e){let t;switch(e.button){case 0:t=this.mouseButtons.LEFT;break;case 1:t=this.mouseButtons.MIDDLE;break;case 2:t=this.mouseButtons.RIGHT;break;default:t=-1}switch(t){case Ei.DOLLY:if(this.enableZoom===!1)return;this._handleMouseDownDolly(e),this.state=$h.DOLLY;break;case Ei.ROTATE:if(e.ctrlKey||e.metaKey||e.shiftKey){if(this.enablePan===!1)return;this._handleMouseDownPan(e),this.state=$h.PAN}else{if(this.enableRotate===!1)return;this._handleMouseDownRotate(e),this.state=$h.ROTATE}break;case Ei.PAN:if(e.ctrlKey||e.metaKey||e.shiftKey){if(this.enableRotate===!1)return;this._handleMouseDownRotate(e),this.state=$h.ROTATE}else{if(this.enablePan===!1)return;this._handleMouseDownPan(e),this.state=$h.PAN}break;default:this.state=$h.NONE}this.state!==$h.NONE&&this.dispatchEvent(Kh)}function og(e){switch(this.state){case $h.ROTATE:if(this.enableRotate===!1)return;this._handleMouseMoveRotate(e);break;case $h.DOLLY:if(this.enableZoom===!1)return;this._handleMouseMoveDolly(e);break;case $h.PAN:if(this.enablePan===!1)return;this._handleMouseMovePan(e);break}}function sg(e){this.enabled===!1||this.enableZoom===!1||this.state!==$h.NONE||(e.preventDefault(),this.dispatchEvent(Kh),this._handleMouseWheel(this._customWheelEvent(e)),this.dispatchEvent(qh))}function cg(e){this.enabled!==!1&&this._handleKeyDown(e)}function lg(e){switch(this._trackPointer(e),this._pointers.length){case 1:switch(this.touches.ONE){case Di.ROTATE:if(this.enableRotate===!1)return;this._handleTouchStartRotate(e),this.state=$h.TOUCH_ROTATE;break;case Di.PAN:if(this.enablePan===!1)return;this._handleTouchStartPan(e),this.state=$h.TOUCH_PAN;break;default:this.state=$h.NONE}break;case 2:switch(this.touches.TWO){case Di.DOLLY_PAN:if(this.enableZoom===!1&&this.enablePan===!1)return;this._handleTouchStartDollyPan(e),this.state=$h.TOUCH_DOLLY_PAN;break;case Di.DOLLY_ROTATE:if(this.enableZoom===!1&&this.enableRotate===!1)return;this._handleTouchStartDollyRotate(e),this.state=$h.TOUCH_DOLLY_ROTATE;break;default:this.state=$h.NONE}break;default:this.state=$h.NONE}this.state!==$h.NONE&&this.dispatchEvent(Kh)}function ug(e){switch(this._trackPointer(e),this.state){case $h.TOUCH_ROTATE:if(this.enableRotate===!1)return;this._handleTouchMoveRotate(e),this.update();break;case $h.TOUCH_PAN:if(this.enablePan===!1)return;this._handleTouchMovePan(e),this.update();break;case $h.TOUCH_DOLLY_PAN:if(this.enableZoom===!1&&this.enablePan===!1)return;this._handleTouchMoveDollyPan(e),this.update();break;case $h.TOUCH_DOLLY_ROTATE:if(this.enableZoom===!1&&this.enableRotate===!1)return;this._handleTouchMoveDollyRotate(e),this.update();break;default:this.state=$h.NONE}}function dg(e){this.enabled!==!1&&e.preventDefault()}function fg(e){e.key===`Control`&&(this._controlActive=!0,this.domElement.getRootNode().addEventListener(`keyup`,this._interceptControlUp,{passive:!0,capture:!0}))}function pg(e){e.key===`Control`&&(this._controlActive=!1,this.domElement.getRootNode().removeEventListener(`keyup`,this._interceptControlUp,{passive:!0,capture:!0}))}var mg=class extends zs{constructor(e,t){super(),this.isViewHelper=!0,this.animating=!1,this.center=new H,this.location={top:null,right:0,bottom:0,left:null};let n=new W(`#ff4466`),r=new W(`#88ff44`),i=new W(`#4488ff`),a=new W(`#000000`),o={},s=[],c=new hf,l=new V,u=new zs,d=new Kd(-2,2,2,-2,0,4);d.position.set(0,0,2);let f=new hu(.04,.04,.8,5).rotateZ(-Math.PI/2).translate(.4,0,0),p=new kl(f,M(n)),m=new kl(f,M(r)),h=new kl(f,M(i));m.rotation.z=Math.PI/2,h.rotation.y=-Math.PI/2,this.add(p),this.add(h),this.add(m);let g=ie(n),_=ie(r),v=ie(i),y=ie(a),b=new sl(g),x=new sl(_),S=new sl(v),C=new sl(y),w=new sl(y),T=new sl(y);b.position.x=1,x.position.y=1,S.position.z=1,C.position.x=-1,w.position.y=-1,T.position.z=-1,C.material.opacity=.2,w.material.opacity=.2,T.material.opacity=.2,b.userData.type=`posX`,x.userData.type=`posY`,S.userData.type=`posZ`,C.userData.type=`negX`,w.userData.type=`negY`,T.userData.type=`negZ`,this.add(b),this.add(x),this.add(S),this.add(C),this.add(w),this.add(T),s.push(b),s.push(x),s.push(S),s.push(C),s.push(w),s.push(T);let E=new H,D=2*Math.PI;this.render=function(n){this.quaternion.copy(e.quaternion).invert(),this.updateMatrixWorld(),E.set(0,0,1),E.applyQuaternion(e.quaternion);let r=this.location,i,a;i=r.left===null?t.offsetWidth-128-r.right:r.left,a=r.top===null?n.isWebGPURenderer?t.offsetHeight-128-r.bottom:r.bottom:n.isWebGPURenderer?r.top:t.offsetHeight-128-r.top,n.clearDepth(),n.getViewport(te),n.setViewport(i,a,128,128),n.render(this,d),n.setViewport(te.x,te.y,te.z,te.w)};let O=new H,k=new Uo,A=new Uo,ee=new Uo,te=new ss,j=0;this.handleClick=function(e){if(this.animating===!0)return!1;let n=t.getBoundingClientRect(),r=this.location,i,a;i=r.left===null?n.left+t.offsetWidth-128-r.right:n.left+r.left,a=r.top===null?n.top+t.offsetHeight-128-r.bottom:n.top+r.top,l.x=(e.clientX-i)/128*2-1,l.y=-((e.clientY-a)/128)*2+1,c.setFromCamera(l,d);let o=c.intersectObjects(s);if(o.length>0){let e=o[0].object;return ne(e,this.center),this.animating=!0,!0}else return!1},this.setLabels=function(e,t,n){o.labelX=e,o.labelY=t,o.labelZ=n,ae()},this.setLabelStyle=function(e,t,n){o.font=e,o.color=t,o.radius=n,ae()},this.update=function(t){let n=t*D;A.rotateTowards(ee,n),e.position.set(0,0,1).applyQuaternion(A).multiplyScalar(j).add(this.center),e.quaternion.rotateTowards(k,n),A.angleTo(ee)===0&&(this.animating=!1)},this.dispose=function(){f.dispose(),p.material.dispose(),m.material.dispose(),h.material.dispose(),b.material.map.dispose(),x.material.map.dispose(),S.material.map.dispose(),C.material.map.dispose(),w.material.map.dispose(),T.material.map.dispose(),b.material.dispose(),x.material.dispose(),S.material.dispose(),C.material.dispose(),w.material.dispose(),T.material.dispose()};function ne(t,n){switch(t.userData.type){case`posX`:O.set(1,0,0),k.setFromEuler(new Ss(0,Math.PI*.5,0));break;case`posY`:O.set(0,1,0),k.setFromEuler(new Ss(-Math.PI*.5,0,0));break;case`posZ`:O.set(0,0,1),k.setFromEuler(new Ss);break;case`negX`:O.set(-1,0,0),k.setFromEuler(new Ss(0,-Math.PI*.5,0));break;case`negY`:O.set(0,-1,0),k.setFromEuler(new Ss(Math.PI*.5,0,0));break;case`negZ`:O.set(0,0,-1),k.setFromEuler(new Ss(0,Math.PI,0));break;default:console.error(`ViewHelper: Invalid axis.`)}j=e.position.distanceTo(n),O.multiplyScalar(j).add(n),u.position.copy(n),u.lookAt(e.position),A.copy(u.quaternion),u.lookAt(O),ee.copy(u.quaternion)}function M(e){return new _l({color:e,toneMapped:!1})}function re(){let e=!1;try{e=typeof OffscreenCanvas<`u`&&new OffscreenCanvas(1,1).getContext(`2d`)!==null}catch{}return e}function N(e,t){let n;return re()?n=new OffscreenCanvas(e,t):(n=document.createElement(`canvas`),n.width=e,n.height=t),n}function ie(e,t){let{font:n=`24px Arial`,color:r=`#000000`,radius:i=14}=o,a=N(64,64),s=a.getContext(`2d`);s.beginPath(),s.arc(32,32,i,0,2*Math.PI),s.closePath(),s.fillStyle=e.getStyle(),s.fill(),t&&(s.font=n,s.textAlign=`center`,s.fillStyle=r,s.fillText(t,32,41));let c=new uu(a);return c.colorSpace=Za,new qc({map:c,toneMapped:!1})}function ae(){b.material.map.dispose(),x.material.map.dispose(),S.material.map.dispose(),b.material.dispose(),x.material.dispose(),S.material.dispose(),b.material=ie(n,o.labelX),x.material=ie(r,o.labelY),S.material=ie(i,o.labelZ)}}},hg={name:`CopyShader`,uniforms:{tDiffuse:{value:null},opacity:{value:1}},vertexShader:`

		varying vec2 vUv;

		void main() {

			vUv = uv;
			gl_Position = projectionMatrix * modelViewMatrix * vec4( position, 1.0 );

		}`,fragmentShader:`

		uniform float opacity;

		uniform sampler2D tDiffuse;

		varying vec2 vUv;

		void main() {

			vec4 texel = texture2D( tDiffuse, vUv );
			gl_FragColor = opacity * texel;


		}`},gg=class{constructor(){this.isPass=!0,this.enabled=!0,this.needsSwap=!0,this.clear=!1,this.renderToScreen=!1}setSize(){}render(){console.error(`THREE.Pass: .render() must be implemented in derived pass.`)}dispose(){}},_g=new Kd(-1,1,1,-1,0,1),vg=new class extends Vc{constructor(){super(),this.setAttribute(`position`,new G([-1,3,0,-1,-1,0,3,-1,0],3)),this.setAttribute(`uv`,new G([0,2,0,0,2,0],2))}},yg=class{constructor(e){this._mesh=new kl(vg,e)}dispose(){this._mesh.geometry.dispose()}render(e){e.render(this._mesh,_g)}get material(){return this._mesh.material}set material(e){this._mesh.material=e}},bg=class extends gg{constructor(e,t=`tDiffuse`){super(),this.textureID=t,this.uniforms=null,this.material=null,e instanceof ud?(this.uniforms=e.uniforms,this.material=e):e&&(this.uniforms=sd.clone(e.uniforms),this.material=new ud({name:e.name===void 0?`unspecified`:e.name,defines:Object.assign({},e.defines),uniforms:this.uniforms,vertexShader:e.vertexShader,fragmentShader:e.fragmentShader})),this._fsQuad=new yg(this.material)}render(e,t,n){this.uniforms[this.textureID]&&(this.uniforms[this.textureID].value=n.texture),this._fsQuad.material=this.material,this.renderToScreen?(e.setRenderTarget(null),this._fsQuad.render(e)):(e.setRenderTarget(t),this.clear&&e.clear(e.autoClearColor,e.autoClearDepth,e.autoClearStencil),this._fsQuad.render(e))}dispose(){this.material.dispose(),this._fsQuad.dispose()}},xg=class extends gg{constructor(e,t){super(),this.scene=e,this.camera=t,this.clear=!0,this.needsSwap=!1,this.inverse=!1}render(e,t,n){let r=e.getContext(),i=e.state;i.buffers.color.setMask(!1),i.buffers.depth.setMask(!1),i.buffers.color.setLocked(!0),i.buffers.depth.setLocked(!0);let a,o;this.inverse?(a=0,o=1):(a=1,o=0),i.buffers.stencil.setTest(!0),i.buffers.stencil.setOp(r.REPLACE,r.REPLACE,r.REPLACE),i.buffers.stencil.setFunc(r.ALWAYS,a,4294967295),i.buffers.stencil.setClear(o),i.buffers.stencil.setLocked(!0),e.setRenderTarget(n),this.clear&&e.clear(),e.render(this.scene,this.camera),e.setRenderTarget(t),this.clear&&e.clear(),e.render(this.scene,this.camera),i.buffers.color.setLocked(!1),i.buffers.depth.setLocked(!1),i.buffers.color.setMask(!0),i.buffers.depth.setMask(!0),i.buffers.stencil.setLocked(!1),i.buffers.stencil.setFunc(r.EQUAL,1,4294967295),i.buffers.stencil.setOp(r.KEEP,r.KEEP,r.KEEP),i.buffers.stencil.setLocked(!0)}},Sg=class extends gg{constructor(){super(),this.needsSwap=!1}render(e){e.state.buffers.stencil.setLocked(!1),e.state.buffers.stencil.setTest(!1)}},Cg=class{constructor(e,t){if(this.renderer=e,this._pixelRatio=e.getPixelRatio(),t===void 0){let n=e.getSize(new V);this._width=n.width,this._height=n.height,t=new ls(this._width*this._pixelRatio,this._height*this._pixelRatio,{type:Wi}),t.texture.name=`EffectComposer.rt1`}else this._width=t.width,this._height=t.height;this.renderTarget1=t,this.renderTarget2=t.clone(),this.renderTarget2.texture.name=`EffectComposer.rt2`,this.writeBuffer=this.renderTarget1,this.readBuffer=this.renderTarget2,this.renderToScreen=!0,this.passes=[],this.copyPass=new bg(hg),this.copyPass.material.blending=0,this.timer=new $d}swapBuffers(){let e=this.readBuffer;this.readBuffer=this.writeBuffer,this.writeBuffer=e}addPass(e){this.passes.push(e),e.setSize(this._width*this._pixelRatio,this._height*this._pixelRatio)}insertPass(e,t){this.passes.splice(t,0,e),e.setSize(this._width*this._pixelRatio,this._height*this._pixelRatio)}removePass(e){let t=this.passes.indexOf(e);t!==-1&&this.passes.splice(t,1)}isLastEnabledPass(e){for(let t=e+1;t<this.passes.length;t++)if(this.passes[t].enabled)return!1;return!0}render(e){this.timer.update(),e===void 0&&(e=this.timer.getDelta());let t=this.renderer.getRenderTarget(),n=!1;for(let t=0,r=this.passes.length;t<r;t++){let r=this.passes[t];if(r.enabled!==!1){if(r.renderToScreen=this.renderToScreen&&this.isLastEnabledPass(t),r.render(this.renderer,this.writeBuffer,this.readBuffer,e,n),r.needsSwap){if(n){let t=this.renderer.getContext(),n=this.renderer.state.buffers.stencil;n.setFunc(t.NOTEQUAL,1,4294967295),this.copyPass.render(this.renderer,this.writeBuffer,this.readBuffer,e),n.setFunc(t.EQUAL,1,4294967295)}this.swapBuffers()}xg!==void 0&&(r instanceof xg?n=!0:r instanceof Sg&&(n=!1))}}this.renderer.setRenderTarget(t)}reset(e){if(e===void 0){let t=this.renderer.getSize(new V);this._pixelRatio=this.renderer.getPixelRatio(),this._width=t.width,this._height=t.height,e=this.renderTarget1.clone(),e.setSize(this._width*this._pixelRatio,this._height*this._pixelRatio)}this.renderTarget1.dispose(),this.renderTarget2.dispose(),this.renderTarget1=e,this.renderTarget2=e.clone(),this.writeBuffer=this.renderTarget1,this.readBuffer=this.renderTarget2}setSize(e,t){this._width=e,this._height=t;let n=this._width*this._pixelRatio,r=this._height*this._pixelRatio;this.renderTarget1.setSize(n,r),this.renderTarget2.setSize(n,r);for(let e=0;e<this.passes.length;e++)this.passes[e].setSize(n,r)}setPixelRatio(e){this._pixelRatio=e,this.setSize(this._width,this._height)}dispose(){this.renderTarget1.dispose(),this.renderTarget2.dispose(),this.copyPass.dispose()}},wg=class extends gg{constructor(e,t,n=null,r=null,i=null){super(),this.scene=e,this.camera=t,this.overrideMaterial=n,this.clearColor=r,this.clearAlpha=i,this.clear=!0,this.clearDepth=!1,this.needsSwap=!1,this.isRenderPass=!0,this._oldClearColor=new W}render(e,t,n){let r=e.autoClear;e.autoClear=!1;let i,a;this.overrideMaterial!==null&&(a=this.scene.overrideMaterial,this.scene.overrideMaterial=this.overrideMaterial),this.clearColor!==null&&(e.getClearColor(this._oldClearColor),e.setClearColor(this.clearColor,e.getClearAlpha())),this.clearAlpha!==null&&(i=e.getClearAlpha(),e.setClearAlpha(this.clearAlpha)),this.clearDepth==1&&e.clearDepth(),e.setRenderTarget(this.renderToScreen?null:n),this.clear===!0&&e.clear(e.autoClearColor,e.autoClearDepth,e.autoClearStencil),e.render(this.scene,this.camera),this.clearColor!==null&&e.setClearColor(this._oldClearColor),this.clearAlpha!==null&&e.setClearAlpha(i),this.overrideMaterial!==null&&(this.scene.overrideMaterial=a),e.autoClear=r}},Tg=class e extends gg{constructor(e,t,n,r){super(),this.renderScene=t,this.renderCamera=n,this.selectedObjects=r===void 0?[]:r,this.visibleEdgeColor=new W(1,1,1),this.hiddenEdgeColor=new W(.1,.04,.02),this.edgeGlow=0,this.usePatternTexture=!1,this.patternTexture=null,this.edgeThickness=1,this.edgeStrength=3,this.downSampleRatio=2,this.pulsePeriod=0,this._visibilityCache=new Map,this._selectionCache=new Set,this.resolution=e===void 0?new V(256,256):new V(e.x,e.y);let i=Math.round(this.resolution.x/this.downSampleRatio),a=Math.round(this.resolution.y/this.downSampleRatio);this.renderTargetMaskBuffer=new ls(this.resolution.x,this.resolution.y),this.renderTargetMaskBuffer.texture.name=`OutlinePass.mask`,this.renderTargetMaskBuffer.texture.generateMipmaps=!1,this.depthMaterial=new pd,this.depthMaterial.side=2,this.depthMaterial.depthPacking=Xa,this.depthMaterial.blending=0,this.prepareMaskMaterial=this._getPrepareMaskMaterial(),this.prepareMaskMaterial.side=2,this.prepareMaskMaterial.fragmentShader=s(this.prepareMaskMaterial.fragmentShader,this.renderCamera),this.renderTargetDepthBuffer=new ls(this.resolution.x,this.resolution.y,{type:Wi}),this.renderTargetDepthBuffer.texture.name=`OutlinePass.depth`,this.renderTargetDepthBuffer.texture.generateMipmaps=!1,this.renderTargetMaskDownSampleBuffer=new ls(i,a,{type:Wi}),this.renderTargetMaskDownSampleBuffer.texture.name=`OutlinePass.depthDownSample`,this.renderTargetMaskDownSampleBuffer.texture.generateMipmaps=!1,this.renderTargetBlurBuffer1=new ls(i,a,{type:Wi}),this.renderTargetBlurBuffer1.texture.name=`OutlinePass.blur1`,this.renderTargetBlurBuffer1.texture.generateMipmaps=!1,this.renderTargetBlurBuffer2=new ls(Math.round(i/2),Math.round(a/2),{type:Wi}),this.renderTargetBlurBuffer2.texture.name=`OutlinePass.blur2`,this.renderTargetBlurBuffer2.texture.generateMipmaps=!1,this.edgeDetectionMaterial=this._getEdgeDetectionMaterial(),this.renderTargetEdgeBuffer1=new ls(i,a,{type:Wi}),this.renderTargetEdgeBuffer1.texture.name=`OutlinePass.edge1`,this.renderTargetEdgeBuffer1.texture.generateMipmaps=!1,this.renderTargetEdgeBuffer2=new ls(Math.round(i/2),Math.round(a/2),{type:Wi}),this.renderTargetEdgeBuffer2.texture.name=`OutlinePass.edge2`,this.renderTargetEdgeBuffer2.texture.generateMipmaps=!1,this.separableBlurMaterial1=this._getSeparableBlurMaterial(4),this.separableBlurMaterial1.uniforms.texSize.value.set(i,a),this.separableBlurMaterial1.uniforms.kernelRadius.value=1,this.separableBlurMaterial2=this._getSeparableBlurMaterial(4),this.separableBlurMaterial2.uniforms.texSize.value.set(Math.round(i/2),Math.round(a/2)),this.separableBlurMaterial2.uniforms.kernelRadius.value=4,this.overlayMaterial=this._getOverlayMaterial();let o=hg;this.copyUniforms=sd.clone(o.uniforms),this.materialCopy=new ud({uniforms:this.copyUniforms,vertexShader:o.vertexShader,fragmentShader:o.fragmentShader,blending:0,depthTest:!1,depthWrite:!1}),this.enabled=!0,this.needsSwap=!1,this._oldClearColor=new W,this.oldClearAlpha=1,this._fsQuad=new yg(null),this.tempPulseColor1=new W,this.tempPulseColor2=new W,this.textureMatrix=new fs;function s(e,t){let n=t.isPerspectiveCamera?`perspective`:`orthographic`;return e.replace(/DEPTH_TO_VIEW_Z/g,n+`DepthToViewZ`)}}dispose(){this.renderTargetMaskBuffer.dispose(),this.renderTargetDepthBuffer.dispose(),this.renderTargetMaskDownSampleBuffer.dispose(),this.renderTargetBlurBuffer1.dispose(),this.renderTargetBlurBuffer2.dispose(),this.renderTargetEdgeBuffer1.dispose(),this.renderTargetEdgeBuffer2.dispose(),this.depthMaterial.dispose(),this.prepareMaskMaterial.dispose(),this.edgeDetectionMaterial.dispose(),this.separableBlurMaterial1.dispose(),this.separableBlurMaterial2.dispose(),this.overlayMaterial.dispose(),this.materialCopy.dispose(),this._fsQuad.dispose()}setSize(e,t){this.renderTargetMaskBuffer.setSize(e,t),this.renderTargetDepthBuffer.setSize(e,t);let n=Math.round(e/this.downSampleRatio),r=Math.round(t/this.downSampleRatio);this.renderTargetMaskDownSampleBuffer.setSize(n,r),this.renderTargetBlurBuffer1.setSize(n,r),this.renderTargetEdgeBuffer1.setSize(n,r),this.separableBlurMaterial1.uniforms.texSize.value.set(n,r),n=Math.round(n/2),r=Math.round(r/2),this.renderTargetBlurBuffer2.setSize(n,r),this.renderTargetEdgeBuffer2.setSize(n,r),this.separableBlurMaterial2.uniforms.texSize.value.set(n,r)}render(t,n,r,i,a){if(this.selectedObjects.length>0){t.getClearColor(this._oldClearColor),this.oldClearAlpha=t.getClearAlpha();let n=t.autoClear;t.autoClear=!1,a&&t.state.buffers.stencil.setTest(!1),t.setClearColor(16777215,1),this._updateSelectionCache(),this._changeVisibilityOfSelectedObjects(!1);let i=this.renderScene.background,o=this.renderScene.overrideMaterial;if(this.renderScene.background=null,this.renderScene.overrideMaterial=this.depthMaterial,t.setRenderTarget(this.renderTargetDepthBuffer),t.clear(),t.render(this.renderScene,this.renderCamera),this._changeVisibilityOfSelectedObjects(!0),this._visibilityCache.clear(),this._updateTextureMatrix(),this._changeVisibilityOfNonSelectedObjects(!1),this.renderScene.overrideMaterial=this.prepareMaskMaterial,this.prepareMaskMaterial.uniforms.cameraNearFar.value.set(this.renderCamera.near,this.renderCamera.far),this.prepareMaskMaterial.uniforms.depthTexture.value=this.renderTargetDepthBuffer.texture,this.prepareMaskMaterial.uniforms.textureMatrix.value=this.textureMatrix,t.setRenderTarget(this.renderTargetMaskBuffer),t.clear(),t.render(this.renderScene,this.renderCamera),this._changeVisibilityOfNonSelectedObjects(!0),this._visibilityCache.clear(),this._selectionCache.clear(),this.renderScene.background=i,this.renderScene.overrideMaterial=o,this._fsQuad.material=this.materialCopy,this.copyUniforms.tDiffuse.value=this.renderTargetMaskBuffer.texture,t.setRenderTarget(this.renderTargetMaskDownSampleBuffer),t.clear(),this._fsQuad.render(t),this.tempPulseColor1.copy(this.visibleEdgeColor),this.tempPulseColor2.copy(this.hiddenEdgeColor),this.pulsePeriod>0){let e=1.25/2+Math.cos(performance.now()*.01/this.pulsePeriod)*.75/2;this.tempPulseColor1.multiplyScalar(e),this.tempPulseColor2.multiplyScalar(e)}this._fsQuad.material=this.edgeDetectionMaterial,this.edgeDetectionMaterial.uniforms.maskTexture.value=this.renderTargetMaskDownSampleBuffer.texture,this.edgeDetectionMaterial.uniforms.texSize.value.set(this.renderTargetMaskDownSampleBuffer.width,this.renderTargetMaskDownSampleBuffer.height),this.edgeDetectionMaterial.uniforms.visibleEdgeColor.value=this.tempPulseColor1,this.edgeDetectionMaterial.uniforms.hiddenEdgeColor.value=this.tempPulseColor2,t.setRenderTarget(this.renderTargetEdgeBuffer1),t.clear(),this._fsQuad.render(t),this._fsQuad.material=this.separableBlurMaterial1,this.separableBlurMaterial1.uniforms.colorTexture.value=this.renderTargetEdgeBuffer1.texture,this.separableBlurMaterial1.uniforms.direction.value=e.BlurDirectionX,this.separableBlurMaterial1.uniforms.kernelRadius.value=this.edgeThickness,t.setRenderTarget(this.renderTargetBlurBuffer1),t.clear(),this._fsQuad.render(t),this.separableBlurMaterial1.uniforms.colorTexture.value=this.renderTargetBlurBuffer1.texture,this.separableBlurMaterial1.uniforms.direction.value=e.BlurDirectionY,t.setRenderTarget(this.renderTargetEdgeBuffer1),t.clear(),this._fsQuad.render(t),this._fsQuad.material=this.separableBlurMaterial2,this.separableBlurMaterial2.uniforms.colorTexture.value=this.renderTargetEdgeBuffer1.texture,this.separableBlurMaterial2.uniforms.direction.value=e.BlurDirectionX,t.setRenderTarget(this.renderTargetBlurBuffer2),t.clear(),this._fsQuad.render(t),this.separableBlurMaterial2.uniforms.colorTexture.value=this.renderTargetBlurBuffer2.texture,this.separableBlurMaterial2.uniforms.direction.value=e.BlurDirectionY,t.setRenderTarget(this.renderTargetEdgeBuffer2),t.clear(),this._fsQuad.render(t),this._fsQuad.material=this.overlayMaterial,this.overlayMaterial.uniforms.maskTexture.value=this.renderTargetMaskBuffer.texture,this.overlayMaterial.uniforms.edgeTexture1.value=this.renderTargetEdgeBuffer1.texture,this.overlayMaterial.uniforms.edgeTexture2.value=this.renderTargetEdgeBuffer2.texture,this.overlayMaterial.uniforms.patternTexture.value=this.patternTexture,this.overlayMaterial.uniforms.edgeStrength.value=this.edgeStrength,this.overlayMaterial.uniforms.edgeGlow.value=this.edgeGlow,this.overlayMaterial.uniforms.usePatternTexture.value=this.usePatternTexture,a&&t.state.buffers.stencil.setTest(!0),t.setRenderTarget(r),this._fsQuad.render(t),t.setClearColor(this._oldClearColor,this.oldClearAlpha),t.autoClear=n}this.renderToScreen&&(this._fsQuad.material=this.materialCopy,this.copyUniforms.tDiffuse.value=r.texture,t.setRenderTarget(null),this._fsQuad.render(t))}_updateSelectionCache(){let e=this._selectionCache;function t(t){t.isMesh&&e.add(t)}e.clear();for(let e=0;e<this.selectedObjects.length;e++)this.selectedObjects[e].traverse(t)}_changeVisibilityOfSelectedObjects(e){let t=this._visibilityCache;for(let n of this._selectionCache)e===!0?n.visible=t.get(n):(t.set(n,n.visible),n.visible=e)}_changeVisibilityOfNonSelectedObjects(e){let t=this._visibilityCache,n=this._selectionCache;function r(r){if(r.isPoints||r.isLine||r.isLine2)e===!0?r.visible=t.get(r):(t.set(r,r.visible),r.visible=e);else if((r.isMesh||r.isSprite)&&!n.has(r)){let n=r.visible;(e===!1||t.get(r)===!0)&&(r.visible=e),t.set(r,n)}}this.renderScene.traverse(r)}_updateTextureMatrix(){this.textureMatrix.set(.5,0,0,.5,0,.5,0,.5,0,0,.5,.5,0,0,0,1),this.textureMatrix.multiply(this.renderCamera.projectionMatrix),this.textureMatrix.multiply(this.renderCamera.matrixWorldInverse)}_getPrepareMaskMaterial(){return new ud({uniforms:{depthTexture:{value:null},cameraNearFar:{value:new V(.5,.5)},textureMatrix:{value:null}},vertexShader:`#include <batching_pars_vertex>
				#include <morphtarget_pars_vertex>
				#include <skinning_pars_vertex>

				varying vec4 projTexCoord;
				varying vec4 vPosition;
				uniform mat4 textureMatrix;

				void main() {

					#include <batching_vertex>
					#include <skinbase_vertex>
					#include <begin_vertex>
					#include <morphtarget_vertex>
					#include <skinning_vertex>
					#include <project_vertex>

					vPosition = mvPosition;

					vec4 worldPosition = vec4( transformed, 1.0 );

					#ifdef USE_INSTANCING

						worldPosition = instanceMatrix * worldPosition;

					#endif

					worldPosition = modelMatrix * worldPosition;

					projTexCoord = textureMatrix * worldPosition;

				}`,fragmentShader:`#include <packing>
				varying vec4 vPosition;
				varying vec4 projTexCoord;
				uniform sampler2D depthTexture;
				uniform vec2 cameraNearFar;

				void main() {

					float depth = unpackRGBAToDepth(texture2DProj( depthTexture, projTexCoord ));
					float viewZ = - DEPTH_TO_VIEW_Z( depth, cameraNearFar.x, cameraNearFar.y );
					float depthTest = (-vPosition.z > viewZ) ? 1.0 : 0.0;
					gl_FragColor = vec4(0.0, depthTest, 1.0, 1.0);

				}`})}_getEdgeDetectionMaterial(){return new ud({uniforms:{maskTexture:{value:null},texSize:{value:new V(.5,.5)},visibleEdgeColor:{value:new H(1,1,1)},hiddenEdgeColor:{value:new H(1,1,1)}},vertexShader:`varying vec2 vUv;

				void main() {
					vUv = uv;
					gl_Position = projectionMatrix * modelViewMatrix * vec4( position, 1.0 );
				}`,fragmentShader:`varying vec2 vUv;

				uniform sampler2D maskTexture;
				uniform vec2 texSize;
				uniform vec3 visibleEdgeColor;
				uniform vec3 hiddenEdgeColor;

				void main() {
					vec2 invSize = 1.0 / texSize;
					vec4 uvOffset = vec4(1.0, 0.0, 0.0, 1.0) * vec4(invSize, invSize);
					vec4 c1 = texture2D( maskTexture, vUv + uvOffset.xy);
					vec4 c2 = texture2D( maskTexture, vUv - uvOffset.xy);
					vec4 c3 = texture2D( maskTexture, vUv + uvOffset.yw);
					vec4 c4 = texture2D( maskTexture, vUv - uvOffset.yw);
					float diff1 = (c1.r - c2.r)*0.5;
					float diff2 = (c3.r - c4.r)*0.5;
					float d = length( vec2(diff1, diff2) );
					float a1 = min(c1.g, c2.g);
					float a2 = min(c3.g, c4.g);
					float visibilityFactor = min(a1, a2);
					vec3 edgeColor = 1.0 - visibilityFactor > 0.001 ? visibleEdgeColor : hiddenEdgeColor;
					gl_FragColor = vec4(edgeColor, 1.0) * vec4(d);
				}`})}_getSeparableBlurMaterial(e){return new ud({defines:{MAX_RADIUS:e},uniforms:{colorTexture:{value:null},texSize:{value:new V(.5,.5)},direction:{value:new V(.5,.5)},kernelRadius:{value:1}},vertexShader:`varying vec2 vUv;

				void main() {
					vUv = uv;
					gl_Position = projectionMatrix * modelViewMatrix * vec4( position, 1.0 );
				}`,fragmentShader:`#include <common>
				varying vec2 vUv;
				uniform sampler2D colorTexture;
				uniform vec2 texSize;
				uniform vec2 direction;
				uniform float kernelRadius;

				float gaussianPdf(in float x, in float sigma) {
					return 0.39894 * exp( -0.5 * x * x/( sigma * sigma))/sigma;
				}

				void main() {
					vec2 invSize = 1.0 / texSize;
					float sigma = kernelRadius/2.0;
					float weightSum = gaussianPdf(0.0, sigma);
					vec4 diffuseSum = texture2D( colorTexture, vUv) * weightSum;
					vec2 delta = direction * invSize * kernelRadius/float(MAX_RADIUS);
					vec2 uvOffset = delta;
					for( int i = 1; i <= MAX_RADIUS; i ++ ) {
						float x = kernelRadius * float(i) / float(MAX_RADIUS);
						float w = gaussianPdf(x, sigma);
						vec4 sample1 = texture2D( colorTexture, vUv + uvOffset);
						vec4 sample2 = texture2D( colorTexture, vUv - uvOffset);
						diffuseSum += ((sample1 + sample2) * w);
						weightSum += (2.0 * w);
						uvOffset += delta;
					}
					gl_FragColor = diffuseSum/weightSum;
				}`})}_getOverlayMaterial(){return new ud({uniforms:{maskTexture:{value:null},edgeTexture1:{value:null},edgeTexture2:{value:null},patternTexture:{value:null},edgeStrength:{value:1},edgeGlow:{value:1},usePatternTexture:{value:0}},vertexShader:`varying vec2 vUv;

				void main() {
					vUv = uv;
					gl_Position = projectionMatrix * modelViewMatrix * vec4( position, 1.0 );
				}`,fragmentShader:`varying vec2 vUv;

				uniform sampler2D maskTexture;
				uniform sampler2D edgeTexture1;
				uniform sampler2D edgeTexture2;
				uniform sampler2D patternTexture;
				uniform float edgeStrength;
				uniform float edgeGlow;
				uniform bool usePatternTexture;

				void main() {
					vec4 edgeValue1 = texture2D(edgeTexture1, vUv);
					vec4 edgeValue2 = texture2D(edgeTexture2, vUv);
					vec4 maskColor = texture2D(maskTexture, vUv);
					vec4 patternColor = texture2D(patternTexture, 6.0 * vUv);
					float visibilityFactor = 1.0 - maskColor.g > 0.0 ? 1.0 : 0.5;
					vec4 edgeValue = edgeValue1 + edgeValue2 * edgeGlow;
					vec4 finalColor = edgeStrength * maskColor.r * edgeValue;
					if(usePatternTexture)
						finalColor += + visibilityFactor * (1.0 - maskColor.r) * (1.0 - patternColor.r);
					gl_FragColor = finalColor;
				}`,blending:2,depthTest:!1,depthWrite:!1,transparent:!0})}};Tg.BlurDirectionX=new V(1,0),Tg.BlurDirectionY=new V(0,1);var Eg={name:`OutputShader`,uniforms:{tDiffuse:{value:null},toneMappingExposure:{value:1}},vertexShader:`
		precision highp float;

		uniform mat4 modelViewMatrix;
		uniform mat4 projectionMatrix;

		attribute vec3 position;
		attribute vec2 uv;

		varying vec2 vUv;

		void main() {

			vUv = uv;
			gl_Position = projectionMatrix * modelViewMatrix * vec4( position, 1.0 );

		}`,fragmentShader:`

		precision highp float;

		uniform sampler2D tDiffuse;

		#include <tonemapping_pars_fragment>
		#include <colorspace_pars_fragment>

		varying vec2 vUv;

		void main() {

			gl_FragColor = texture2D( tDiffuse, vUv );

			// tone mapping

			#ifdef LINEAR_TONE_MAPPING

				gl_FragColor.rgb = LinearToneMapping( gl_FragColor.rgb );

			#elif defined( REINHARD_TONE_MAPPING )

				gl_FragColor.rgb = ReinhardToneMapping( gl_FragColor.rgb );

			#elif defined( CINEON_TONE_MAPPING )

				gl_FragColor.rgb = CineonToneMapping( gl_FragColor.rgb );

			#elif defined( ACES_FILMIC_TONE_MAPPING )

				gl_FragColor.rgb = ACESFilmicToneMapping( gl_FragColor.rgb );

			#elif defined( AGX_TONE_MAPPING )

				gl_FragColor.rgb = AgXToneMapping( gl_FragColor.rgb );

			#elif defined( NEUTRAL_TONE_MAPPING )

				gl_FragColor.rgb = NeutralToneMapping( gl_FragColor.rgb );

			#elif defined( CUSTOM_TONE_MAPPING )

				gl_FragColor.rgb = CustomToneMapping( gl_FragColor.rgb );

			#endif

			// color space

			#ifdef SRGB_TRANSFER

				gl_FragColor = sRGBTransferOETF( gl_FragColor );

			#endif

		}`},Dg=class extends gg{constructor(){super(),this.isOutputPass=!0,this.uniforms=sd.clone(Eg.uniforms),this.material=new dd({name:Eg.name,uniforms:this.uniforms,vertexShader:Eg.vertexShader,fragmentShader:Eg.fragmentShader}),this._fsQuad=new yg(this.material),this._outputColorSpace=null,this._toneMapping=null}render(e,t,n){this.uniforms.tDiffuse.value=n.texture,this.uniforms.toneMappingExposure.value=e.toneMappingExposure,(this._outputColorSpace!==e.outputColorSpace||this._toneMapping!==e.toneMapping)&&(this._outputColorSpace=e.outputColorSpace,this._toneMapping=e.toneMapping,this.material.defines={},Xo.getTransfer(this._outputColorSpace)===`srgb`&&(this.material.defines.SRGB_TRANSFER=``),this._toneMapping===1?this.material.defines.LINEAR_TONE_MAPPING=``:this._toneMapping===2?this.material.defines.REINHARD_TONE_MAPPING=``:this._toneMapping===3?this.material.defines.CINEON_TONE_MAPPING=``:this._toneMapping===4?this.material.defines.ACES_FILMIC_TONE_MAPPING=``:this._toneMapping===6?this.material.defines.AGX_TONE_MAPPING=``:this._toneMapping===7?this.material.defines.NEUTRAL_TONE_MAPPING=``:this._toneMapping===5&&(this.material.defines.CUSTOM_TONE_MAPPING=``),this.material.needsUpdate=!0),this.renderToScreen===!0?(e.setRenderTarget(null),this._fsQuad.render(e)):(e.setRenderTarget(t),this.clear&&e.clear(e.autoClearColor,e.autoClearDepth,e.autoClearStencil),this._fsQuad.render(e))}dispose(){this.material.dispose(),this._fsQuad.dispose()}},Og=Object.freeze([`X`,`Y`,`Z`,`RX`,`RY`,`RZ`]),kg=Object.freeze([`fixed`,`one-way`,`spring`,`free`]),Ag=`free`,jg=`fixed`,Mg=`spring`,Ng=`one-way`,Pg=1e-12;function Fg(e){let t=e?.direction;if(!Array.isArray(t))return null;let n=[0,1,2].map(e=>Number(t[e]));return n.every(e=>Number.isFinite(e))&&n.some(e=>Math.abs(e)>Pg)?n:null}function Ig(e){let t=Array.isArray(e?.stiffness_matrix)?e.stiffness_matrix.map(Number):[];if(t.length>0)return Og.map((e,n)=>Number.isFinite(t[n])&&Math.abs(t[n])>0);let n=Number(e?.stiffness),r=Fg(e);return!Number.isFinite(n)||Math.abs(n)<=0||!r?Og.map(()=>!1):[...r.map(e=>Math.abs(e)>Pg),!1,!1,!1]}function Lg(e){return![!1,0,`0`,`x`,`X`,null,void 0].includes(e)}function Rg(e={}){let t=e?.dof_states;if(Array.isArray(t)&&t.length===Og.length&&t.every(e=>kg.includes(e)))return t.slice();let n=String(e.support_type??e.type??`custom`).toLowerCase(),r=n===`fixed`?`anchor`:n,i=Ig(e),a=e=>e.map((e,t)=>e===Ag&&i[t]?Mg:e);if(Array.isArray(e.blocked_dof))return a(Og.map((t,n)=>Lg(e.blocked_dof[n])?jg:Ag));if(r===`anchor`)return Og.map(()=>jg);if(r===`spring`)return a(Og.map(()=>Ag));let o=Fg(e);if(r===`rest`){let e=o?o.findIndex(e=>Math.abs(e)>Pg):2;return a(Og.map((t,n)=>n===e?Ng:Ag))}return a(o?[...o.map(e=>Math.abs(e)>Pg?jg:Ag),Ag,Ag,Ag]:[jg,jg,jg,Ag,Ag,Ag])}function zg(e={}){return Rg(e).map(e=>e===jg||e===Ng)}function Bg(e){return String(e?.source??``).toLowerCase()===`tuba.support`}var Vg=Object.freeze([`#2563eb`,`#059669`,`#d97706`,`#7c3aed`,`#0891b2`,`#e11d48`,`#4f46e5`,`#0d9488`,`#ea580c`,`#64748b`]),Hg=Object.freeze([{id:`default`,label:`Default (Role)`},{id:`section`,label:`Section`},{id:`material`,label:`Material`},{id:`group`,label:`Group`},{id:`insulation`,label:`Insulation`}]);function Ug(e,t){if(!e||!t||t==="default")return null;if(t===`section`)return e.metadata?.section||e.metadata?.profile?.kind||null;if(t===`material`)return e.metadata?.material||null;if(t===`group`)return e.group_ids?.[0]||e.metadata?.groups?.[0]||e.metadata?.group||null;if(t===`insulation`){let t=e.metadata?.insulation;if(!t)return`Uninsulated / Bare`;if(t.material){let e=Number(t.thickness_m);return Number.isFinite(e)&&e>0?`${t.material} (${Math.round(e*1e3)} mm)`:t.material}return t.id||`Insulated`}return e[t]||e.metadata?.[t]||null}function Wg(e){let t=String(e?.kind||``);return t===`pipe`||t===`element`||t===`rack_member`}function Gg(e,t=e?.modelColorBy||`default`){if(!t||t==="default")return{mode:`default`,items:[],colorByValue:new Map,colorByObjectId:new Map};let n=(e?.objects||[]).filter(Wg),r=new Map,i=new Map;for(let e of n){let n=Ug(e,t)||`Unassigned`;r.set(n,(r.get(n)||0)+1),i.has(n)||i.set(n,[]),i.get(n).push(e.id)}let a=[...r.keys()].sort((e,t)=>e.localeCompare(t)),o=[],s=new Map,c=new Map;return a.forEach((e,t)=>{let n=Vg[t%Vg.length];s.set(e,n);let a=i.get(e)||[];o.push({value:e,label:e,color:n,count:r.get(e)||0,objectIds:a});for(let e of a)c.set(e,n)}),{mode:t,items:o,colorByValue:s,colorByObjectId:c}}function Kg(e,t=[]){let n=e?.modelColorBy;if(!n||n==="default"||Be(e)!==`model`)return null;let r=Array.isArray(t)?t:[t],i=Gg(e,n);for(let e of r)if(i.colorByObjectId.has(e))return i.colorByObjectId.get(e);for(let t of r){let r=(e?.objects||[]).find(e=>e.id===t),a=m(r),o=(e?.objects||[]).find(e=>Wg(e)&&m(e)===a);if(o&&i.colorByObjectId.has(o.id))return i.colorByObjectId.get(o.id);if(r){let e=Ug(r,n)||`Unassigned`;if(i.colorByValue.has(e))return i.colorByValue.get(e)}}return null}var qg=new Set([`aabb`,`cuboid`,`cylinder`,`label`,`line`,`line_load_comb`,`marker`,`mesh`,`point`,`polyline`,`tube`,`tube_envelope`,`tuyau_subpoint_glyphs`,`vector`]),Jg=10265519,Yg=.32,Xg={iso:[1,-1,.65],positiveX:[1,0,0],negativeX:[-1,0,0],positiveY:[0,1,0],negativeY:[0,-1,0],positiveZ:[0,0,1],negativeZ:[0,0,-1]},Zg=`viewer.webgl2_unavailable`;function Qg(e,t={}){let n=new Js;n.background=new W(t.backgroundColor??16317180);let r=new Bs;r.name=`TubaSceneRoot`,n.add(r);let i=jv(e.bounds)??Mv(e.geometryAssets??[]),a=new Map((e.geometryPayloads??[]).map(e=>[e.asset_id,e])),o=new Set(e.visibleObjectIds??[]),s={...e,canvasFactory:t.canvasFactory??(()=>globalThis.document?.createElement(`canvas`)),hasVisualDeformedGeometry:dv(e,a,o)},c=new Map,l=[],u=0;for(let t of e.geometryAssets??[]){let n=a.get(t.id)??{};if(!lv(t,o)||!uv(t,n,e.activeGeometryStateId))continue;let i=L_(t,n,s);if(i.diagnostic&&l.push(i.diagnostic),i.object){cv(i.object,t,i.format),r.add(i.object),u+=1;for(let e of t.object_ids??[])c.set(e,i.object)}}zv(r,e);let d=new Map((e.objects??[]).map(e=>[e.id,m(e)])),f=new Set((e.objects??[]).filter(e=>e.kind===`support`).map(e=>e.id)),p=new Set((e.objects??[]).filter(e=>String(m(e)).startsWith(`element:`)).map(e=>e.id)),h=new Set((e.objects??[]).filter(e=>String(e.kind).includes(`analysis_mesh`)).map(e=>e.id)),g=new Set((e.objects??[]).filter(e=>p.has(e.id)&&!h.has(e.id)&&c.has(e.id)).map(m)),_=new Map;for(let e of r.children){for(let t of e.userData.objectIds??[]){let n=d.get(t)??t;_.has(n)||_.set(n,new Set),_.get(n).add(e)}let t=(e.userData.objectIds??[]).some(e=>f.has(e)),r=(e.userData.objectIds??[]).some(e=>p.has(e)),i=r&&(e.userData.objectIds??[]).some(e=>!h.has(e)||!g.has(d.get(e)));if(e.userData.outlineSurface=i,t&&!e.userData.contactStatus||!r&&e.userData.pickVolume){let t=new xf(e.userData.pickVolume??e,x_);t.material.depthTest=!1,t.renderOrder=40,t.visible=!1,t.raycast=()=>{},e.userData.highlightOutline=t,n.add(t)}(t||r)&&e.traverse(e=>{e.userData.preserveHighlightColor=!0})}let v=$g(r)??i,y=[...r.children],b=V_(r);return b&&r.add(b),sv(n,v,e.referenceGridVisible!==!1),{bounds:v,deformationPreview:b,diagnostics:l,objectsByObjectId:c,keysById:d,objectsBySelectionKey:_,renderableObjects:y,renderedObjectCount:u,root:r,scene:n}}function $g(e){if(e.children.length===0)return null;let t=e.children.filter(e=>e.userData?.format!==`vector`),n=new lc;for(let r of t.length>0?t:e.children)n.expandByObject(r,!0);return n.isEmpty()||!Number.isFinite(n.min.x)||!Number.isFinite(n.max.x)?null:[n.min.x,n.min.y,n.min.z,n.max.x,n.max.y,n.max.z]}var e_=[`bounds`,`geometryAssets`,`geometryPayloads`,`overlays`,`activeLoadCase`,`activeResultStateId`,`activeGeometryStateId`,`coloring`,`modelColorBy`,`colorChannel`,`resultVectorScales`,`bodyOpacity`,`contactArrows`,`contactNeutral`];function t_(e,t=()=>{}){let n=null,r=null;return{get(i){let a=n?.visibleObjectIds!==i?.visibleObjectIds&&n_(n)!==n_(i);if(!r||a||e_.some(e=>n?.[e]!==i?.[e])){let n=r;r=e(i),n&&t(n)}return n=i,r},clear(){r&&t(r),n=null,r=null}}}function n_(e){return e?dv(e,new Map((e.geometryPayloads??[]).map(e=>[e.asset_id,e])),new Set(e.visibleObjectIds??[])):!1}function r_(e,t={}){let n=e.getContext?.(`webgl2`,{antialias:!0,preserveDrawingBuffer:!0});if(!n){let e=Error(`This browser could not start WebGL2.`);throw e.code=Zg,e}let r=new Wh({antialias:!0,canvas:e,context:n,preserveDrawingBuffer:!0});r.setClearColor(t.backgroundColor??16317180,1),r.setPixelRatio(Math.min(globalThis.devicePixelRatio??1,2)),r.localClippingEnabled=!0;let i=i_(e),a=Lv(1),o=new tg(a,e);o.enableDamping=!1,r.autoClear=!1;let s=new mg(a,e);s.setLabels(`X`,`Y`,`Z`);let c=null,l=null,u=null,d=[],f=!1,p=null,m=new H,h=()=>{let n=Math.max(1,Math.floor(e.clientWidth||e.width||1)),i=Math.max(1,Math.floor(e.clientHeight||e.height||1));M_(a,n,i,t.viewportInsets?.()??{});let o=r.getSize(new V);return o.x===n&&o.y===i?!1:(r.setSize(n,i,!1),l?.setSize(n,i),!0)},g=t=>{r.clear();let n=t.renderableObjects.filter(e=>e.visible&&e.userData.outlineSurface),o=n.filter(e=>e.userData.selected&&!e.userData.hovered),c=n.filter(e=>e.userData.hovered);if(o.length||c.length){if(!l){l=new Cg(r),u=new wg(t.scene,a),l.addPass(u);for(let e of[x_,b_]){let n=new Tg(r.getSize(new V),t.scene,a);n.visibleEdgeColor.setHex(e),n.hiddenEdgeColor.setHex(e),n.overlayMaterial.blending=1,n.overlayMaterial.premultipliedAlpha=!0,n.edgeStrength=1,d.push(n),l.addPass(n)}l.addPass(new Dg)}u.scene=t.scene,d.forEach((e,n)=>{e.renderScene=t.scene,e.selectedObjects=n===0?o:c,e.enabled=e.selectedObjects.length>0}),l.render()}else r.render(t.scene,a);s.render(r),f&&a_(i,t.deformationPreview,a),e.dataset.cameraDirection=a.getWorldDirection(m).toArray().map(e=>e.toFixed(3)).join(`,`)},_=()=>{p===null&&(p=requestAnimationFrame(()=>{p=null,c&&g(c)}))},v=()=>{s.update(1/60),o.update(),c&&g(c),s.animating&&requestAnimationFrame(v)};o.addEventListener(`change`,_),(typeof ResizeObserver>`u`?null:new ResizeObserver(()=>{h()&&c&&g(c)}))?.observe(e);let y=t_(e=>Qg(e,t),o_),b=s_(a,o);return{render(t){h(),c&&!y_(c,t)&&(y.clear(),c=null);let n=y.get(t);return H_(n.root,t,{previewOnly:f}),p_(n,t),f&&__(n,!0),h_(n,t.sectionBox),b.apply(t,n.bounds),o.update(),n.camera=a,E_(n,t.selectedObjectIds??[]),g(n),c=n,e.dataset.renderer=`three`,e.dataset.renderedObjects=String(n.renderedObjectCount),e.dataset.renderDiagnostics=String(n.diagnostics.length),n},redraw(){_()},setDeformationInteraction(e){return f===e||!g_(c,e)?!1:(f=e,c&&__(c,e),i.canvas&&(i.canvas.hidden=!e),e?g(c):i.context?.clearRect(0,0,i.canvas.width,i.canvas.height),!0)},renderDeformation(e){return!f||!c?.deformationPreview?!1:(H_(c.root,e,{previewOnly:!0}),a_(i,c.deformationPreview,a),!0)},handleGizmoClick(e){return s.center.copy(o.target),s.handleClick(e)?(requestAnimationFrame(v),!0):!1},resetView(){c&&(h(),N_(a,c.bounds,o),g(c))},setStandardView(e){c&&(h(),P_(a,c.bounds,o,e),g(c))},zoomBy(e){I_(a,e)&&c&&g(c)},orbitBy(e,t){F_(a,o.target,e,t)&&(o.update(),c&&g(c))}}}function i_(e){let t=e.ownerDocument?.createElement?.(`canvas`),n=t?.getContext?.(`2d`);return!t||!n||!e.parentElement?{canvas:null,context:null}:(t.dataset.deformationPreview=``,t.hidden=!0,e.insertAdjacentElement(`afterend`,t),{canvas:t,context:n})}function a_(e,t,n){if(!e?.canvas||!e.context||e.canvas.hidden||!t)return;let r=e.canvas.previousElementSibling;if(!r)return;(e.canvas.width!==r.width||e.canvas.height!==r.height)&&(e.canvas.width=r.width,e.canvas.height=r.height);let{canvas:i,context:a}=e,o=t.geometry.getAttribute(`position`),s=new H;a.clearRect(0,0,i.width,i.height),a.beginPath();for(let e=0;e+1<o.count;e+=2)s.fromBufferAttribute(o,e).applyMatrix4(t.matrixWorld).project(n),a.moveTo((s.x+1)*i.width/2,(1-s.y)*i.height/2),s.fromBufferAttribute(o,e+1).applyMatrix4(t.matrixWorld).project(n),a.lineTo((s.x+1)*i.width/2,(1-s.y)*i.height/2);a.strokeStyle=`#7c3aed`,a.lineCap=`round`,a.lineJoin=`round`,a.lineWidth=Math.max(6,6*(globalThis.devicePixelRatio??1)),a.stroke()}function o_(e){let t=new Set,n=new Set,r=new Set;e?.scene?.traverse(e=>{e.geometry&&t.add(e.geometry);for(let t of Array.isArray(e.material)?e.material:e.material?[e.material]:[])n.add(t),t.map&&r.add(t.map)});for(let e of t)e.dispose();for(let e of n)e.dispose();for(let e of r)e.dispose()}function s_(e,t=null){let n=!1,r=null;return{apply(i,a){let o=i?.camera?.fitRequest;return n?!o||o.id===r?null:(r=o.id,N_(e,o.bounds,t)):(n=!0,r=o?.id??null,N_(e,o?.bounds??a,t))}}}var c_=6,l_=1;function u_(e,t,n){return d_(e,t,n)?.objectId??null}function d_(e,t,n){if(!e?.camera||!e.renderableObjects?.length)return null;let r=new hf,i=new V(t.x/n.width*2-1,-(t.y/n.height)*2+1);e.camera.updateProjectionMatrix(),e.camera.updateMatrixWorld(),e.scene?.updateMatrixWorld(!0),r.setFromCamera(i,e.camera),r.params.Line.threshold=c_*f_(e,n);let a=e.renderableObjects.filter(e=>e.visible!==!1&&e.userData?.pickable!==!1&&e.userData?.format!==`tuyau_subpoint_glyphs`),o=r.intersectObjects(a,!0),s=null,c=null;for(let e of o){if((e.object.material?.clippingPlanes??[]).some(t=>t.distanceToPoint(e.point)<0))continue;let t=e.object.userData?.primaryObjectId||e.object.userData?.objectId;if(t){if(e.object.userData.pickVolumeHit){c??={objectId:t,point:e.point.toArray()};continue}if(e.object.userData?.pickPriority===l_)return{objectId:t,point:e.point.toArray()};s===null&&(s={objectId:t,point:e.point.toArray()})}}return c??s}function f_(e,t){let n=e.camera;return n.isOrthographicCamera?(n.top-n.bottom)/n.zoom/t.height:2*n.position.distanceTo(Nv(e.bounds)??new H)*Math.tan(Ho.degToRad(n.fov)/2)/t.height}function p_(e,t){let n=new Set(t.visibleObjectIds??[]),r=0;for(let t of e.renderableObjects??[]){let e=t.userData?.objectIds??[];t.visible=e.length===0||e.some(e=>n.has(e)),t.visible&&(r+=1)}return e.renderedObjectCount=r,e}function m_(e){if(!e)return[];let{min:t,max:n}=e;return[new Gl(new H(-1,0,0),n[0]),new Gl(new H(1,0,0),-t[0]),new Gl(new H(0,-1,0),n[1]),new Gl(new H(0,1,0),-t[1]),new Gl(new H(0,0,-1),n[2]),new Gl(new H(0,0,1),-t[2])]}function h_(e,t){let n=t?m_(t):null;e.root?.traverse(e=>{e.userData?.volumeMeshEdges&&(e.visible=!!t);let r=Array.isArray(e.material)?e.material:e.material?[e.material]:[];for(let e of r)e.clippingPlanes=n,e.needsUpdate=!0})}function g_(e,t){return t?!!e?.deformationPreview&&!(e.renderableObjects??[]).some(e=>e.userData?.sectionDeformation):!0}function __(e,t){for(let n of e.renderableObjects??[])!n.userData?.undeformedReference&&!v_(n)||(t?(Object.hasOwn(n.userData,`visibleBeforeDeformationPreview`)||(n.userData.visibleBeforeDeformationPreview=n.visible),n.visible=!1):Object.hasOwn(n.userData,`visibleBeforeDeformationPreview`)&&(n.visible=n.userData.visibleBeforeDeformationPreview,delete n.userData.visibleBeforeDeformationPreview));return e}function v_(e){let t=!1;return e.traverse(e=>{t||=!!e.userData?.visualDeformationSourceScale}),t}function y_(e,t){let n=new Set((e.renderableObjects??[]).map(e=>e.userData?.assetId)),r=new Set(t.visibleObjectIds??[]),i=new Map((t.geometryPayloads??[]).map(e=>[e.asset_id,e]));return(t.geometryAssets??[]).filter(e=>lv(e,r)).filter(e=>uv(e,i.get(e.id)??{},t.activeGeometryStateId)).every(e=>n.has(e.id))}var b_=1920728,x_=16096779;function S_(e,t){if(e.highlightedObjectId===(t??null))return e;for(let t of C_(e,e.highlightedObjectId))w_(t,!1);e.highlightedObjectId=t??null;for(let n of C_(e,t))w_(n,!0);return e}function C_(e,t){return e.objectsBySelectionKey?.get(e.keysById?.get(t)??t)??[e.objectsByObjectId?.get(t)].filter(Boolean)}function w_(e,t){e&&(e.traverse(e=>{D_(e,t,e.userData.selected===!0)}),T_(e))}function T_(e){let t=e.userData.highlightOutline;t&&(t.visible=e.visible&&(e.userData.hovered||e.userData.selected),t.visible&&t.update(),t.material.color.setHex(e.userData.hovered?b_:x_))}function E_(e,t=[]){let n=new Set(t);e.selectedObjectIds=[...n];let r=new Set([...n].flatMap(t=>[...C_(e,t)]));for(let t of e.renderableObjects??[]){let e=r.has(t)||(t.userData.objectIds??[]).some(e=>n.has(e));t.userData.selected=e,t.traverse(t=>{D_(t,t.userData.hovered===!0,e)}),T_(t)}return e}function D_(e,t,n){e.userData.hovered=t,e.userData.selected=n;let r=Array.isArray(e.material)?e.material:e.material?[e.material]:[];for(let i of r)O_(i,t,n,e)}function O_(e,t,n,r){if(r?.userData.preserveHighlightColor)return;let i=t?b_:n?x_:null;if(e.emissive){e.emissive.setHex(i??0);return}!e.color||e.isSpriteMaterial||r?.isInstancedMesh||e.vertexColors||(Object.hasOwn(e.userData,`baseColorHex`)||(e.userData.baseColorHex=e.color.getHex()),e.color.setHex(i??e.userData.baseColorHex))}function k_(e,t,n){let r=Nv(e),i=t.clone().normalize(),a=n.clone().normalize();Math.abs(i.dot(a))>.999&&(a=new H(0,1,0));let o=new H().crossVectors(a,i).normalize();a=new H().crossVectors(i,o).normalize();let s=new H,c=0,l=0,u=0;for(let t=0;t<8;t+=1)s.set(t&1?e[3]:e[0],t&2?e[4]:e[1],t&4?e[5]:e[2]).sub(r),c=Math.max(c,Math.abs(s.dot(o))),l=Math.max(l,Math.abs(s.dot(a))),u=Math.max(u,Math.abs(s.dot(i)));return{halfWidth:c,halfHeight:l,halfDepth:u}}var A_=1.1;function j_(e=`iso`){return Math.abs(Xg[e]?.[2]??0)===1?new H(0,1,0):new H(0,0,1)}function M_(e,t,n,r={}){if(e.userData.viewportSize={width:t,height:n},e.userData.viewportInsets=r,e.userData.viewportAspect=t/n,e.isOrthographicCamera){let i=e.userData.fitHalfHeight??1;e.left=-i*t/n,e.right=i*t/n,e.top=i,e.bottom=-i;let a=e=>Math.max(0,Number(r[e])||0);e.setViewOffset(t,n,(a(`right`)-a(`left`))/2,(a(`bottom`)-a(`top`))/2,t,n)}else e.aspect=t/n,e.updateProjectionMatrix()}function N_(e,t,n=null,r=`iso`){let i=jv(t)??[-1,-1,-1,1,1,1],a=Nv(i),o=Pv(i),s=Math.max(o.length()*.5,.5),c=new H(...Xg[r]??Xg.iso).normalize(),l=j_(r),u=k_(i,c,l),d;if(e.isOrthographicCamera){let t=Iv(e.userData.viewportAspect)??1,n=e.userData.viewportSize,r=e.userData.viewportInsets??{},i=Math.max(0,Number(r.left)||0),a=Math.max(0,Number(r.right)||0),o=Math.max(0,Number(r.top)||0),c=Math.max(0,Number(r.bottom)||0),l=Math.max(1,(n?.width??1)-i-a),f=Math.max(1,(n?.height??1)-o-c),p=n?l/f:t,m=Math.max(Math.max(u.halfHeight,u.halfWidth/p)*A_,1e-4);e.zoom=1,e.userData.fitHalfHeight=n?m*n.height/f:m,n?M_(e,n.width,n.height,r):(e.left=-m*t,e.right=m*t,e.top=m,e.bottom=-m),d=Math.max(u.halfDepth*2+s,1)}else{let t=Ho.degToRad(e.fov||45),n=Iv(e.aspect)??1,r=u.halfHeight*A_/Math.tan(t/2),i=u.halfWidth*A_/(Math.tan(t/2)*n);d=Math.max(r,i)+u.halfDepth,d=Math.max(d,.001)}return e.near=Math.max(d/1e3,.001),e.far=d*1e3,e.up.copy(l),e.position.copy(a).addScaledVector(c,d),e.lookAt(a),e.updateProjectionMatrix(),e.userData.fitBounds=i,n&&(n.target.copy(a),n.update()),{distance:d,radius:s,target:a.toArray()}}function P_(e,t,n=null,r=`iso`){let i=N_(e,t,n,r),a=new H(...i.target),o=new H(...Xg[r]??Xg.iso).normalize();e.up.copy(j_(r)),e.position.copy(a).addScaledVector(o,i.distance),e.lookAt(a),e.updateProjectionMatrix(),n&&(n.target.copy(a),n.update())}function F_(e,t,n,r){if(!Number.isFinite(n)||!Number.isFinite(r))return!1;let i=e.position.clone().sub(t),a=new vf().setFromVector3(new H(i.x,i.z,-i.y));a.theta+=n,a.phi=Ho.clamp(a.phi+r,.02,Math.PI-.02);let o=new H().setFromSpherical(a);return e.position.copy(t).add(new H(o.x,-o.z,o.y)),e.up.set(0,0,1),e.lookAt(t),e.updateProjectionMatrix(),!0}function I_(e,t){return!e.isOrthographicCamera||!Number.isFinite(t)||t<=0?!1:(e.zoom=Ho.clamp(e.zoom*t,.05,20),e.updateProjectionMatrix(),!0)}function L_(e,t,n){let r=String(e.format??``).toLowerCase();if(!qg.has(r))return Rv(e,`Unsupported geometry format '${e.format}'.`);let i=pv(e,t,n),a=i.section_deformations?null:z_(e,t,i),o=a?.sourceConfig??i;try{let s=R_(e,t,n,r,o);if(s.object&&(s.object.userData.undeformedReference=fv(e,i,n)),s.object&&i.section_deformations&&Cv(e,i))s.object.userData.sectionDeformation=i,H_(s.object,n);else if(s.object&&a){let i=R_(e,t,n,r,a.baseConfig);i.object&&B_(s.object,i.object,a.sourceScale)&&H_(s.object,n)}return s}catch(t){return Rv(e,t.message)}}function R_(e,t,n,r,i){return r===`tube`||r===`tube_envelope`?U_(e,i,r):r===`polyline`||r===`line`?W_(e,i,r):r===`label`?K_(e,i,r,n):r===`point`||r===`marker`?G_(e,i,r,n):r===`tuyau_subpoint_glyphs`?ev(e,i,r,n):r===`vector`?tv(e,i,r,n):r===`line_load_comb`?nv(e,i,r,n):r===`cuboid`||r===`aabb`?rv(e,i,r):r===`cylinder`?iv(e,i,r):r===`mesh`?av(e,i,t,r,n):Rv(e,`No renderer for geometry format '${e.format}'.`)}function z_(e,t,n){let r=String(e.format??``).toLowerCase();if(r!==`polyline`&&r!==`line`&&r!==`tube`&&r!==`tube_envelope`&&r!==`mesh`)return null;let i={...t.generation_config??{},...e.generation_config??{}};if(!Cv(e,i))return null;let a=Iv(i.visual_scale??i.deformation_scale??i.displacement_scale),o=r===`mesh`?`vertices`:`points`,s=r===`mesh`?`base_vertices`:`base_points`,c=wv(i[o]),l=wv(i[s]??(r===`mesh`?void 0:i.cold_points));return!a||c.length<2||l.length!==c.length?null:{sourceScale:a,sourceConfig:{...n,[o]:c,visual_scale_display_only:a},baseConfig:{...n,[o]:l,visual_scale_display_only:0}}}function B_(e,t,n){let r=[],i=[];e.traverse(e=>{e.geometry?.getAttribute(`position`)&&r.push(e)}),t.traverse(e=>{e.geometry?.getAttribute(`position`)&&i.push(e)});let a=!1;for(let e=0;e<Math.min(r.length,i.length);e+=1){let t=r[e],o=i[e],s=t.geometry.getAttribute(`position`),c=o.geometry.getAttribute(`position`);if(s.count!==c.count)continue;if(t.userData.visualDeformationSourceScale=n,t.isLine){t.userData.visualDeformationPositions={base:c.array.slice(),source:s.array.slice()},a=!0;continue}t.geometry.morphAttributes.position=[c];let l=t.geometry.getAttribute(`normal`),u=o.geometry.getAttribute(`normal`);l&&u?.count===l.count&&(t.geometry.morphAttributes.normal=[u]),t.updateMorphTargets?.(),a=!0}return a}function V_(e){let t=[];for(let n of e.children){let e=n.userData?.visualDeformationPositions;if(e)for(let r=0;r<e.base.length/3-1;r+=1)for(let i of[r,r+1])t.push({base:e.base.slice(i*3,i*3+3),source:e.source.slice(i*3,i*3+3),sourceScale:n.userData.visualDeformationSourceScale})}if(t.length===0)return null;let n=new Vc;n.setAttribute(`position`,new G(t.flatMap(({source:e})=>[...e]),3));let r=new cu(n,new Xl({color:8141549,depthTest:!1,transparent:!0}));return r.name=`VisualDeformationPreview`,r.renderOrder=1e3,r.visible=!1,r.userData.visualDeformationPreview=t,r}function H_(e,t,n={}){let r=Vt(t);e?.traverse(e=>{let t=e.userData?.visualDeformationPreview;if(t){let n=e.geometry.getAttribute(`position`);for(let e=0;e<t.length;e+=1){let{base:i,source:a,sourceScale:o}=t[e],s=r/o;n.setXYZ(e,i[0]+(a[0]-i[0])*s,i[1]+(a[1]-i[1])*s,i[2]+(a[2]-i[2])*s)}n.needsUpdate=!0;return}let i=e.userData?.sectionDeformation;if(i){let t=bv(i,r),n=e.geometry.getAttribute(`position`);t.forEach((e,t)=>n.setXYZ(t,...e)),n.needsUpdate=!0,e.isMesh&&e.geometry.computeVertexNormals(),e.geometry.computeBoundingBox(),e.geometry.computeBoundingSphere();return}if(n.previewOnly)return;let a=Iv(e.userData?.visualDeformationSourceScale);if(!a)return;let o=e.userData.visualDeformationPositions;if(o){let t=e.geometry.getAttribute(`position`),n=r/a;for(let e=0;e<t.array.length;e+=1)t.array[e]=o.base[e]+(o.source[e]-o.base[e])*n;t.needsUpdate=!0,e.geometry.computeBoundingBox(),e.geometry.computeBoundingSphere()}else e.morphTargetInfluences&&(e.morphTargetInfluences[0]=1-r/a)})}function U_(e,t,n){let r=kv(t.points);if(r.length<2)return Rv(e,`Tube assets require at least two points.`);let i=Iv(t.radius_m)??Fv(e.bounds,.035),a=new ju(r),o=Math.max(8,r.length*12),s=new kl(new $u(a,o,i,14,!1),mv(e,t,{transparent:n===`tube_envelope`&&t.envelope_type!==`insulation`})),c=Iv(t.inner_radius_m);if(!c||c>=i)return s.name=e.id,{format:n,object:s};let l=new Bs,u=mv(e,t);u.side=1,l.add(s,new kl(new $u(a,o,c,14,!1),u));let d=mv(e,t);d.side=2;let f=new H(0,0,1);for(let e of[0,1]){let t=new Xu(c,i,28);t.applyQuaternion(new Uo().setFromUnitVectors(f,a.getTangent(e).normalize())),t.translate(...a.getPoint(e).toArray()),l.add(new kl(t,d))}return l.name=e.id,{format:n,object:l}}function W_(e,t,n){let r=kv(t.points);if(r.length<2)return Rv(e,`Polyline assets require at least two points.`);let i=new Vc().setFromPoints(r),a=Ev(t,1);if(String(t.source??``).toLowerCase()===`tuba.support_link`){let o=r[0].distanceTo(r[1]),s=new iu(i,new hd({color:hv(e,t),dashSize:Math.max(o*.08,.001),gapSize:Math.max(o*.05,.001),depthWrite:!1,opacity:a,transparent:!0}));return s.computeLineDistances(),s.name=e.id,s.userData.supportLink=`attachment`,{format:n,object:s}}let o=String(t.source??``).includes(`analysis_mesh`)||String(e.id??``).includes(`analysis_mesh`),s=new iu(i,new Xl({color:hv(e,t),depthTest:!o,depthWrite:!o&&a>=1&&!t.transparent,linewidth:o?3:2,opacity:a,transparent:!!(t.transparent||a<1||o)}));return o&&(s.renderOrder=500),s.name=e.id,{format:n,object:s}}function G_(e,t,n,r){let i=Av(t.point??t.location??t.clash?.location)??Nv(e.bounds);if(!i)return Rv(e,`Point assets require a point or valid bounds.`);if(Bg(t))return Z_(e,t,n,i,r);let a=String(t.source??``).includes(`analysis_mesh`)||String(e.id??``).includes(`analysis_mesh`),o=new Zu(Iv(t.radius_m)??Fv(e.bounds,n===`marker`?.06:a?.025:.035),16,12);o.computeBoundingSphere();let s=mv(e,t);a&&(s.depthTest=!1);let c=new kl(o,s);return a&&(c.renderOrder=501),c.position.copy(i),c.name=e.id,{format:n,object:c}}function K_(e,t,n,r){let i=typeof t.text==`string`?t.text:``,a=Av(t.position),o=Iv(t.height);if(!i||!a||!o)return Rv(e,`Label assets require text, position, and a positive height.`);let s=r.canvasFactory?.(),c=s?.getContext?.(`2d`);if(!c)return Rv(e,`Label rendering requires a 2D canvas context.`);c.font=`600 64px sans-serif`,s.width=Math.ceil(c.measureText(i).width+36),s.height=100,c.font=`600 64px sans-serif`,c.fillStyle=`rgba(15, 23, 42, 0.86)`,c.fillRect(0,0,s.width,s.height),c.fillStyle=`#ffffff`,c.textAlign=`center`,c.textBaseline=`middle`,c.fillText(i,s.width/2,s.height/2);let l=new sl(new qc({map:new uu(s),depthTest:!1,transparent:!0}));return l.position.copy(a),l.scale.set(o*s.width/s.height,o,1),l.renderOrder=1100,l.name=e.id,l.userData.pickable=!1,{format:n,object:l}}function q_(e,t,n,r=null,i=.1,a=!1){let o=(n?.canvasFactory??(()=>globalThis.document?.createElement?.(`canvas`)))();if(!o)return null;let s=o.getContext?.(`2d`);if(!s)return null;s.font=`600 44px "IBM Plex Mono", monospace, sans-serif`;let c=s.measureText?s.measureText(e).width:110;o.width=Math.ceil(c+44),o.height=68,s.font=`600 44px "IBM Plex Mono", monospace, sans-serif`;let l=`rgba(245, 158, 11, 0.8)`,u=`#fef3c7`;a?(l=`rgba(220, 38, 38, 0.9)`,u=`#fecaca`):r===`sticking`?(l=`rgba(59, 130, 246, 0.85)`,u=`#dbeafe`):r===`sliding`?(l=`rgba(20, 184, 166, 0.85)`,u=`#ccfbf1`):r===`open`&&(l=`rgba(148, 163, 184, 0.7)`,u=`#cbd5e1`),s.fillStyle=`rgba(15, 23, 42, 0.88)`,typeof s.roundRect==`function`?(s.beginPath(),s.roundRect(0,0,o.width,o.height,10),s.fill(),s.strokeStyle=l,s.lineWidth=3,s.stroke()):s.fillRect(0,0,o.width,o.height),s.fillStyle=u,s.textAlign=`center`,s.textBaseline=`middle`,s.fillText(e,o.width/2,o.height/2+1);let d=new sl(new qc({map:new uu(o),depthTest:!1,depthWrite:!1,transparent:!0}));d.position.copy(t);let f=Math.max(i*.45,.04);return d.scale.set(f*o.width/o.height,f,1),d.renderOrder=1100,d.userData.supportPart=`friction-badge`,d}function J_(e,t,n,r=`force`,i=.1){let a=(n?.canvasFactory??(()=>globalThis.document?.createElement?.(`canvas`)))();if(!a)return null;let o=a.getContext?.(`2d`);if(!o)return null;o.font=`600 44px "IBM Plex Mono", monospace, sans-serif`;let s=o.measureText?o.measureText(e).width:110;a.width=Math.ceil(s+44),a.height=68,o.font=`600 44px "IBM Plex Mono", monospace, sans-serif`;let c=`rgba(59, 130, 246, 0.85)`,l=`#dbeafe`;r===`moment`?(c=`rgba(20, 184, 166, 0.85)`,l=`#ccfbf1`):r===`line_load`&&(c=`rgba(2, 132, 199, 0.85)`,l=`#e0f2fe`),o.fillStyle=`rgba(15, 23, 42, 0.90)`,typeof o.roundRect==`function`?(o.beginPath(),o.roundRect(0,0,a.width,a.height,10),o.fill(),o.strokeStyle=c,o.lineWidth=3,o.stroke()):o.fillRect(0,0,a.width,a.height),o.fillStyle=l,o.textAlign=`center`,o.textBaseline=`middle`,o.fillText(e,a.width/2,a.height/2+1);let u=new sl(new qc({map:new uu(a),depthTest:!1,depthWrite:!1,transparent:!0}));u.position.copy(t);let d=Math.max(i*.45,.04);return u.scale.set(d*a.width/a.height,d,1),u.renderOrder=1100,u.name=`${r}-badge`,u.userData.loadPart=`load-badge`,u.userData.pickable=!1,u}function Y_(e,t,n){let r=t,i=n;t>=1e3&&(r=t/1e3,i=n===`N`?`kN`:n===`N·m`?`kN·m`:`kN/m`);let a;return Math.abs(r-Math.round(r))<1e-4?a=String(Math.round(r)):(a=r.toFixed(1),a.endsWith(`.0`)&&(a=a.slice(0,-2))),`${e} = ${a} ${i}`}function X_(e,t){if(t.badge_text)return String(t.badge_text);if(e===`force`){if(t.vector_kind!==`force`&&t.quantity!==`force`&&!t.source?.includes(`applied_loads`))return null;let e=Array.isArray(t.components)?t.components.map(Number):null,n=Number(t.magnitude);return!Number.isFinite(n)&&e&&(n=Math.hypot(...e)),!Number.isFinite(n)||n<=0?null:Y_(`F`,n,`N`)}if(e===`moment`){if(t.vector_kind!==`moment`&&t.quantity!==`moment`&&!String(t.result_type??``).endsWith(`_moment`))return null;let e=Array.isArray(t.components)?t.components.map(Number):null,n=Number(t.magnitude);return!Number.isFinite(n)&&e&&(n=Math.hypot(...e)),!Number.isFinite(n)||n<=0?null:Y_(`M`,n,`N·m`)}if(e===`line_load`){let e=Number(t.value_npm??t.value);return!Number.isFinite(e)||Math.abs(e)<=0?null:Y_(`q`,Math.abs(e),`N/m`)}return null}function Z_(e,t,n,r,i){let a=String(t.support_type??`custom`).toLowerCase(),o=a===`fixed`?`anchor`:a,s=Pv(i?.bounds??e.bounds),c=Math.max(s.x,s.y,s.z),l=Math.max((Iv(t.radius_m)??0)*1.5,Ho.clamp(c*.018,.08,.3)),u=Q_(Number.parseInt(An.restraint.slice(1),16)),d=Q_(Number.parseInt(An.spring.slice(1),16)),f=Q_(Number.parseInt(An.prescribed.slice(1),16),{wireframe:!0,opacity:.9}),p=new Bs;p.name=e.id,p.position.copy(r),p.renderOrder=20,p.userData.supportGlyph=`dof`,p.userData.pickPriority=l_,p.userData.supportType=o,p.userData.supportAttachment=t.attached_to?`attached`:`ground`;let m=(e,t,n,r=null)=>{let i=new kl(e,n);return r&&i.position.copy(r),i.userData.supportPart=t,p.add(i),i},h=[new H(1,0,0),new H(0,1,0),new H(0,0,1)],g=zg(t);if(g.every(Boolean))m(new mu(l*2,l*2,l*2),`fixed-block`,u);else{for(let e=0;e<3;e+=1)if(g[e])for(let t of[-1,1]){let n=h[e],r=m(new gu(l,l*2,24),`restraint-cone`,u,n.clone().multiplyScalar(t*l*2));r.quaternion.setFromUnitVectors(new H(0,1,0),n.clone().multiplyScalar(-t)),r.userData.supportAxis=e,r.userData.supportSide=t}for(let e=3;e<6;e+=1){if(!g[e])continue;let t=m(new Qu(l*.85,l*.18,8,24),`restraint-rotation`,u);t.quaternion.setFromUnitVectors(new H(0,0,1),h[e-3]),t.userData.supportAxis=e}}let _=Array.isArray(t.stiffness_matrix)?t.stiffness_matrix.map(Number):[];for(let e=0;e<3;e+=1)!Number.isFinite(_[e])||Math.abs(_[e])<=0||$_(m,h[e],l,d,e);if(_.length===0&&Number.isFinite(Number(t.stiffness))&&Math.abs(Number(t.stiffness))>0){let e=Av(t.direction);e?.lengthSq()>1e-12&&$_(m,e.normalize(),l,d,`direction`)}for(let e=3;e<6;e+=1){if(!Number.isFinite(_[e])||Math.abs(_[e])<=0)continue;let t=m(new Qu(l*1.25,l*.22,8,24),`spring-rotation`,d);t.quaternion.setFromUnitVectors(new H(0,0,1),h[e-3]),t.userData.supportAxis=e}let v=Av(t.imposed_displacement);if(v?.lengthSq()>1e-12){let e=v.normalize();m(new gu(l,l*3,24),`prescribed-displacement`,f,e.clone().multiplyScalar(l*1.5)).quaternion.setFromUnitVectors(new H(0,1,0),e)}let y=Number(t.friction_coefficient),b=Number.isFinite(y)&&y>0;if(o===`rest`&&(b||t.attached_to||t.normal_stiffness!=null)){let n=Av(t.contact_normal??t.direction)??new H(0,0,1),r=n.lengthSq()>1e-12?n.clone().normalize():new H(0,0,1),a=Math.abs(r.z)>=.8?2:+(Math.abs(r.y)>=.8),o=null,s=!1;if(i){let n=mn(i)[t.support_id??t.id??e.id?.split(`:`).pop()];n&&(o=n.status,s=Number(n.utilization)>1.001)}let c=l*2.2,u=l*2.6,d=l*.16,f=Iv(t.radius_m)??l*.7,h=r.clone().multiplyScalar(-f-d/2),g=new Uo().setFromUnitVectors(new H(0,0,1),r),_=b?14251782:14329120;s?_=14427686:o===`sticking`?_=2450411:o===`sliding`?_=1013358:o===`open`&&(_=6583435);let v=new fd({color:_,roughness:.35,metalness:.25,depthTest:!0,transparent:o===`open`,opacity:o===`open`?.45:.95}),x=m(new mu(c,u,d),`contact-shoe-pad`,v,h);x.quaternion.copy(g),x.userData.supportAxis=a;let S=s?16557477:o===`sticking`?9684477:o===`sliding`?6220500:o===`open`?9741240:b?16708551:16777215,C=new cu(new xu(new mu(c,u,d)),new Xl({color:S,transparent:!0,opacity:.85}));x.add(C);let w=c*.36,T=u*.36,E=d/2+.001,D=new cu(new Vc().setFromPoints([new H(-w,0,E),new H(w,0,E),new H(0,-T,E),new H(0,T,E)]),new Xl({color:16777215,transparent:!0,opacity:.85}));if(D.name=`sliding-plane-guides`,x.add(D),b){let e=`μ = ${y.toFixed(2)}`;o&&(e=`${o===`sticking`?`■`:o===`sliding`?`➜`:`○`} ${e}`);let t=Math.abs(r.x)<.9?new H(1,0,0):new H(0,1,0),n=new H().crossVectors(r,t).normalize(),a=h.clone().add(n.multiplyScalar(c*.85)),u=q_(e,a,i,o,l,s);u&&p.add(u)}}if(!t.attached_to){p.updateMatrixWorld(!0);let e=new lc().setFromObject(p),t=Number.isFinite(e.min.z)?e.min.z-p.position.z:-l,n=l*.18,r=m(new mu(l*2.4,l*2.4,n),`ground-hatch`,u,new H(0,0,t-l*.12-n/2));r.userData.supportAxis=2}return{format:n,object:p}}function Q_(e,{transparent:t=!0,opacity:n=.5,wireframe:r=!1}={}){return new _l({color:e,depthTest:!0,depthWrite:!1,opacity:n,transparent:t,wireframe:r})}function $_(e,t,n,r,i){for(let a of[-3,-2,2,3]){let o=e(new Qu(n,n*.5,10,28),`spring-ring`,r,t.clone().multiplyScalar(a*n));o.quaternion.setFromUnitVectors(new H(0,0,1),t),o.userData.supportAxis=i}}function ev(e,t,n,r){let i=kv(t.starts??t.start_points),a=kv(t.ends??t.end_points),o=Math.min(i.length,a.length);if(o<1)return Rv(e,`TUYAU sub-point glyph assets require start and end point arrays.`);let s=Iv(t.radius_m)??.006,c=new Vl(new hu(s,s,1,Math.max(4,Math.min(16,Math.floor(Number(t.radial_segments)||8))),1,!1),new _l({color:16777215,opacity:Ev(t,.94),transparent:!0}),o),l=new fs,u=new H,d=new H,f=new H(1,1,1),p=new Uo,m=new H(0,1,0),h=Array.isArray(t.values)?t.values.map(Number):[],g=gv(t,h,r),_=0;for(let n=0;n<o;n+=1){d.copy(a[n]).sub(i[n]);let r=d.length();r<=1e-12||(u.copy(i[n]).add(a[n]).multiplyScalar(.5),p.setFromUnitVectors(m,d.normalize()),f.set(1,r,1),l.compose(u,p,f),c.setMatrixAt(_,l),c.setColorAt(_,new W(_v(h[n],g,e,t))),_+=1)}return c.count=_,c.instanceMatrix.needsUpdate=!0,c.instanceColor&&(c.instanceColor.needsUpdate=!0),c.name=e.id,{format:n,object:c}}function tv(e,t,n,r){let i=Av(t.start),a=Av(t.end);if(!i||!a)return Rv(e,`Vector assets require start and end points.`);let o=a.clone().sub(i),s=o.length();if(s<=1e-12)return Rv(e,`Vector assets require non-zero length.`);let c=o.normalize(),l=hv(e,t),u=Math.min(s*.25,.18),d=Math.min(s*.12,.08);if(t.vector_kind===`moment`||String(t.result_type??``).endsWith(`_moment`)){let a=new H(0,1,0),o=new Bs;o.position.copy(i),o.quaternion.setFromUnitVectors(a,c),o.userData.pickPriority=l_;let f=new Tf(a,new H,s,l,u,d);f.name=`moment-axis`;let p=s*.22,m=-Math.PI/4,h=Math.PI*1.5,g=Array.from({length:33},(e,t)=>{let n=m+h*t/32;return new H(p*Math.cos(n),0,-p*Math.sin(n))}),_=new kl(new $u(new ju(g),32,s*.012,10,!1),new _l({color:l}));_.name=`moment-rotation-arc`;let v=m+h,y=new H(-Math.sin(v),0,-Math.cos(v)).normalize(),b=s*.12,x=new kl(new gu(s*.045,b,16),new _l({color:l}));x.position.copy(g.at(-1)).addScaledVector(y,b/2),x.quaternion.setFromUnitVectors(a,y),x.name=`moment-rotation-head`,o.add(f,_,x);let S=X_(`moment`,t);if(S){let e=J_(S,new H(p+.08,s*.5,0),r,`moment`,Math.max(s*.25,.1));e&&o.add(e)}return o.name=e.id,{format:n,object:o}}let f=new Tf(c,i,s,l,u,d);f.userData.pickPriority=l_;let p=X_(`force`,t);if(p){let e=Math.abs(c.z)<.9?new H(0,0,1):new H(0,1,0),t=new H().crossVectors(c,e).normalize(),n=Math.max(d*1.6,.08),a=J_(p,i.clone().addScaledVector(c,s*.5).addScaledVector(t,n).clone().sub(i),r,`force`,Math.max(s*.25,.1));a&&f.add(a)}return f.name=e.id,{format:n,object:f}}function nv(e,t,n,r){let i=kv(t.arrow_starts),a=kv(t.arrow_ends);if(!i.length||i.length!==a.length)return Rv(e,`Line load comb assets require matching arrow_starts and arrow_ends points.`);let o=hv(e,t),s=new Bs;s.userData.pickPriority=l_;for(let e=0;e<i.length;e+=1){let t=i[e],n=a[e].clone().sub(t),r=n.length();if(r<=1e-12)continue;let c=new Tf(n.normalize(),t,r,o,Math.min(r*.28,.18),Math.min(r*.14,.09));c.name=`line-load-arrow`,s.add(c)}let c=kv(t.crest_points??t.arrow_starts);if(c.length>=2){let e=new iu(new Vc().setFromPoints(c),new Xl({color:o}));e.name=`line-load-crest`,s.add(e)}let l=new lc().setFromObject(s);if(!l.isEmpty()){let e=Math.max(...i.map((e,t)=>e.distanceTo(a[t])))*.25,t=l.getSize(new H).max(new H(e,e,e)),n=new kl(new mu(t.x,t.y,t.z),new _l({visible:!1,side:2}));n.name=`line-load-pick-volume`,n.position.copy(l.getCenter(new H)),n.userData.pickVolumeHit=!0,s.add(n),s.userData.pickVolume=n}let u=t.show_badge!==!1,d=X_(`line_load`,t);if(u&&d&&c.length>=1&&i.length>=1){let e=c[Math.floor(c.length/2)].clone(),t=a[0].clone().sub(i[0]),n=t.length(),o=n>1e-6?t.normalize():new H(0,0,-1),l=J_(d,e.addScaledVector(o,-Math.max(n*.3,.09)),r,`line_load`,Math.max(n*.4,.12));l&&s.add(l)}return s.name=e.id,{format:n,object:s}}function rv(e,t,n){let r=jv(t.bounds??t.obstacle?.bounds??e.bounds);if(!r)return Rv(e,`Box assets require valid bounds.`);let i=Pv(r),a=new mu(Math.max(i.x,1e-6),Math.max(i.y,1e-6),Math.max(i.z,1e-6)),o=new kl(a,mv(e,t,{transparent:!0}));o.position.copy(Nv(r)),o.name=e.id;let s=new cu(new xu(a),new Xl({color:Ov(hv(e,t))}));return o.add(s),{format:n,object:o}}function iv(e,t,n){let r=jv(t.bounds??t.obstacle?.bounds??e.bounds);if(!r)return Rv(e,`Cylinder assets require valid bounds.`);let i=Pv(r),a=[i.x,i.y,i.z],o=a.indexOf(Math.max(...a)),s=Math.min(...a.filter((e,t)=>t!==o))/2;if(!(s>1e-6))return Rv(e,`Cylinder assets require a positive radius.`);let c=new hu(s,s,Math.max(a[o],1e-6),32,1,!1),l=new kl(c,mv(e,t,{transparent:!0}));l.position.copy(Nv(r)),o===0?l.rotation.z=Math.PI/2:o===2&&(l.rotation.x=Math.PI/2),l.name=e.id;let u=new cu(new xu(c,30),new Xl({color:Ov(hv(e,t))}));return l.add(u),{format:n,object:l}}function av(e,t,n,r,i){let a=t.vertices??n.vertices??t.mesh?.vertices,o=t.triangles??t.faces??t.indices??n.faces??n.indices??t.mesh?.faces;if(!Array.isArray(a)||a.length<3)return Rv(e,`Mesh assets require vertices.`);let s=a.flat();if(!s.every(Number.isFinite))return Rv(e,`Mesh vertices must be finite numbers.`);let c=new Vc;c.setAttribute(`position`,new G(s,3)),Array.isArray(o)&&o.length>0&&c.setIndex(o.flatMap(e=>Array.isArray(e)&&e.length===4?[e[0],e[1],e[2],e[0],e[2],e[3]]:e)),c.computeVertexNormals();let l={opacity:1,...t},u=mv(e,l);u.side=2;let d=Array.isArray(t.vertex_values)?t.vertex_values.map(Number):[];if(d.length===a.length&&d.every(Number.isFinite)){let n=gv(t,d,i),r=d.flatMap(r=>{let i=new W(_v(r,n,e,t));return[i.r,i.g,i.b]});c.setAttribute(`color`,new G(r,3)),u.vertexColors=!0}let f=new kl(c,u);if(t.show_edges){u.polygonOffset=!0,u.polygonOffsetFactor=1,u.polygonOffsetUnits=1;let n=Ev(l,1),r=t.surface_edge_indices,i;Array.isArray(r)&&r.length>0?(i=new Vc,i.setAttribute(`position`,c.getAttribute(`position`)),i.setIndex(r.flat())):i=new ed(c),f.add(new cu(i,ov(e,l,n)))}let p=t.volume_vertices,m=t.volume_edge_indices;if(Array.isArray(p)&&p.length>0&&Array.isArray(m)&&m.length>0){let t=new Vc;t.setAttribute(`position`,new G(p.flat(),3)),t.setIndex(m.flat());let n=new cu(t,ov(e,l));n.userData.volumeMeshEdges=!0,n.visible=!1,f.add(n)}return f.name=e.id,{format:r,object:f}}function ov(e,t,n=Ev(t,1)){return new Xl({color:2042167,depthWrite:!1,opacity:n,transparent:n<1})}function sv(e,t,n=!0){let r=Pv(t),i=Math.max(r.x,r.y,r.z,1),a=Nv(t);e.add(new Nd(16777215,9147555,2.1));let o=new Jd(16777215,2.4);if(o.position.set(a.x+i,a.y-i,a.z+i),e.add(o),n){let n=new yf(i*1.05,10,12108496,14804975);n.rotation.x=Math.PI/2,n.position.set(a.x,a.y,t[2]-i*.03),e.add(n)}}function cv(e,t,n){let r={assetId:t.id,bounds:t.bounds??null,format:n,pickPriority:e.userData?.pickPriority??0,objectId:t.object_ids?.[0]??null,objectIds:[...t.object_ids??[]],primaryObjectId:t.object_ids?.[0]??null};e.traverse(e=>{e.userData={...e.userData,...r}})}function lv(e,t){let n=e.object_ids??[];return n.length===0||n.some(e=>t.has(e))}function uv(e,t,n){let r={...t?.generation_config??{},...e?.generation_config??{}}.geometry_state_id??null;return r===null||r===n}function dv(e,t=new Map,n=new Set(e.visibleObjectIds??[])){return(e.geometryAssets??[]).some(r=>{if(!lv(r,n))return!1;let i=t.get(r.id)??{};return uv(r,i,e.activeGeometryStateId)?Cv(r,{...i.generation_config??{},...r.generation_config??{}}):!1})}function fv(e,t,n){return(typeof n.hasVisualDeformedGeometry==`boolean`?n.hasVisualDeformedGeometry:dv(n))&&String(t.source??``).toLowerCase()===`tuba.element`}function pv(e,t={},n={}){let r={...t.generation_config??{},...e.generation_config??{}};if(String(e.format??``).toLowerCase()!==`tuyau_subpoint_glyphs`){let t=[r.node_id,r.element_id&&`object:element:${r.element_id}`].filter(Boolean).map(String),i=Lt(n,e.object_ids??[],t);if(i!==null)r.color=i;else{let t=Kg(n,e.object_ids??[]);t!==null&&(r.color=Dv(t)??t)}}fv(e,r,n)&&(r.color=Jg,r.opacity=Yg,r.transparent=!0);let i=Ir(n,e.object_ids??[]);if(i!==null&&i<1){let e=Number(r.opacity);r.opacity=Number.isFinite(e)?Math.min(e,i):i,r.transparent=!0}return String(e.format??``).toLowerCase()===`vector`?yv(e,r,n):xv(e,r,n)}function mv(e,t,n={}){let r=Ev(t,n.transparent?.48:.92),i=!!(n.transparent||t.transparent||r<1);return new fd({color:hv(e,t),depthWrite:!i,metalness:.05,opacity:r,roughness:.68,transparent:i})}function hv(e,t){let n=Dv(t.color);if(n!==null)return n;if(t.issue_id||t.clash||e.id?.includes(`:clash:`))return 14427686;let r=String(t.source??``);return r===`tuba.support`?16096779:e.format===`vector`?12592851:r.includes(`analysis_mesh`)?366185:r.includes(`deformed`)?8141549:r.includes(`obstacle`)||e.id?.includes(`:obstacle:`)?6583435:e.format===`aabb`||e.format===`cuboid`?9741240:e.format===`line_load_comb`?165063:2450411}function gv(e,t,n){let r=Et(n),i=e.range??e.legend?.range??vv(t);return r?.overlay?.data?.result_type===`tuyau_subpoints`?r:{field:e.legend?.field??`VMIS`,unit:e.legend?.unit??`Pa`,range:i,colorMap:e.legend?.color_map??`turbo`,thresholds:e.legend?.thresholds??{}}}function _v(e,t,n,r){return zt(Number(e),t)??hv(n,r)}function vv(e){let t=e.filter(Number.isFinite);return t.length===0?{min:0,max:1}:{min:Math.min(...t),max:Math.max(...t)}}function yv(e,t,n){let r=Tv(t.start),i=Tv(t.end);if(!r||!i)return t;let a=Bt(n,Sv(e,t));return a===1?t:{...t,end:r.map((e,t)=>e+(i[t]-e)*a)}}function bv(e,t){let n=e.base_vertices??e.base_points,r=n.length/e.section_origins.length;return n.map((n,i)=>{let a=Math.floor(i/r),o=new H(...e.section_origins[a]),s=e.section_deformations[a],c=new H(...s.slice(3)).multiplyScalar(t),l=c.length(),u=new H(...n).sub(o);return l>1e-15&&u.applyAxisAngle(c.divideScalar(l),l),u.add(o).add(new H(...s.slice(0,3)).multiplyScalar(t)).toArray()})}function xv(e,t,n){if(!Cv(e,t))return t;let r=wv(t.points);if(r.length<2)return t;let i=Iv(t.visual_scale??t.deformation_scale??t.displacement_scale),a=Vt(n);if(!i||Math.abs(a-i)<=1e-12)return{...t,visual_scale_display_only:a};let o=wv(t.base_points??t.cold_points);if(o.length!==r.length)return{...t,visual_scale_display_only:i};let s=r.map((e,t)=>{let n=o[t];return e.map((e,t)=>n[t]+(e-n[t])*(a/i))});return{...t,points:s,visual_scale_display_only:a}}function Sv(e,t){let n=`${e.id??``} ${t.source??``} ${t.result_type??``} ${t.resultType??``}`.toLowerCase();return t.vector_kind===`moment`||n.includes(`moment`)?`moment`:n.includes(`reaction`)||n.includes(`forc_noda`)?`reaction`:n.includes(`displacement`)||n.includes(`depl`)?`displacement`:`vector`}function Cv(e,t){let n=e.layer_ids??t.layer_ids??[],r=`${e.id??``} ${t.source??``} ${t.purpose??``} ${t.geometry_state_id??``}`.toLowerCase();return n.some(e=>String(e).includes(`deformed:visual`))||r.includes(`visual`)||r.includes(`deformed`)&&Iv(t.visual_scale??t.deformation_scale??t.displacement_scale)>1}function wv(e){return Array.isArray(e)?e.map(Tv).filter(Boolean):[]}function Tv(e){if(!Array.isArray(e)||e.length<3)return null;let t=e.slice(0,3).map(Number);return t.every(Number.isFinite)?t:null}function Ev(e,t){let n=Number(e.opacity);return Number.isFinite(n)?Math.max(0,Math.min(1,n)):t}function Dv(e){if(typeof e==`number`&&Number.isFinite(e))return e;if(typeof e!=`string`)return null;let t=e.trim().replace(/^#/,``);return/^[0-9a-f]{6}$/i.test(t)?Number.parseInt(t,16):null}function Ov(e){let t=new W(e);return t.multiplyScalar(.65),t}function kv(e){return Array.isArray(e)?e.map(Av).filter(Boolean):[]}function Av(e){if(!Array.isArray(e)||e.length<3)return null;let t=e.slice(0,3).map(Number);return t.every(Number.isFinite)?new H(t[0],t[1],t[2]):null}function jv(e){if(!Array.isArray(e)||e.length!==6)return null;let t=e.map(Number);return t.every(Number.isFinite)?[Math.min(t[0],t[3]),Math.min(t[1],t[4]),Math.min(t[2],t[5]),Math.max(t[0],t[3]),Math.max(t[1],t[4]),Math.max(t[2],t[5])]:null}function Mv(e){let t=e.map(e=>jv(e.bounds)).filter(Boolean);return t.length===0?[-1,-1,-1,1,1,1]:t.reduce((e,t)=>[Math.min(e[0],t[0]),Math.min(e[1],t[1]),Math.min(e[2],t[2]),Math.max(e[3],t[3]),Math.max(e[4],t[4]),Math.max(e[5],t[5])],t[0])}function Nv(e){let t=jv(e);return t?new H((t[0]+t[3])/2,(t[1]+t[4])/2,(t[2]+t[5])/2):null}function Pv(e){let t=jv(e)??[-1,-1,-1,1,1,1];return new H(Math.max(t[3]-t[0],1e-6),Math.max(t[4]-t[1],1e-6),Math.max(t[5]-t[2],1e-6))}function Fv(e,t){let n=Pv(e),r=Math.min(n.x,n.y,n.z)/2;return r>1e-6?r:t}function Iv(e){let t=Number(e);return Number.isFinite(t)&&t>0?t:null}function Lv(e){let t=Iv(e)??1,n=new Kd(-t,t,1,-1,.01,1e4);return n.up.set(0,0,1),n.userData.viewportAspect=t,n}function Rv(e,t){return{diagnostic:{assetId:e.id,code:`renderer.invalid_asset`,message:t,severity:`error`},format:e.format,object:null}}function zv(e,t){let n=vt(t)?.overlay?.id;if(n&&Array.isArray(t.visibleOverlayIds)&&!t.visibleOverlayIds.includes(n))return;let r=yn(t),i=Pv(t.bounds),a=Math.max(i.x,i.y,i.z,1)*.025;for(let n of Object.values(mn(t))){let i=hn(t,n.support_id);if(!(t.visibleObjectIds??[]).includes(i))continue;let o=(t.objects??[]).find(e=>e.id===i),s=(t.geometryAssets??[]).find(e=>e.id===o?.geometry_asset_id);if(!s)continue;let c=(t.geometryPayloads??[]).find(e=>e.asset_id===s.id),l={...s.generation_config,...c?.generation_config},u=Av(l.point??l.location)??Nv(s.bounds);if(!u)continue;let d=new Bs;d.position.copy(u),d.userData={objectIds:[i],format:`vector`,contactStatus:n.status,pickPriority:l_};let f=n.utilization>1.001?14427686:sn[n.status]??sn.indeterminate,p=new _l({color:f,depthTest:!1}),m=null;if(n.status===`open`)m=new kl(new Qu(a*.45,a*.08,8,24),p);else if(n.status===`sliding`)m=new Tf(new H(...n.tangential_force).normalize(),new H,a,f,a*.5,a*.35);else if(n.status!==`sticking`){m=new Bs,m.add(new kl(new Qu(a*.3,a*.07,8,16,Math.PI*1.5),p));let e=new kl(new Zu(a*.08,8,8),p);e.position.y=-a*.45,m.add(e)}m&&d.add(m);for(let[e,i,o]of[[`normal`,n.normal.map(e=>e*n.normal_force),2450411],[`tangential`,n.tangential_force,1013358]]){let n=new H(...i),s=n.length();if(t.contactArrows?.[e]===!1||!(s>0)||!(r[e]>0))continue;let c=new Tf(n.normalize(),new H,a*8*s/r[e],o);c.userData.contactForce=e,d.add(c)}d.traverse(e=>{e.userData.objectIds=[i],e.userData.primaryObjectId=i,e.userData.pickPriority=l_,e.renderOrder=30}),e.add(d)}}var Bv=`tuba.review_record.v1`,Vv=Object.freeze([{id:`open`,label:`Open`,requiresReason:!1,description:`Not yet examined.`},{id:`reviewing`,label:`Reviewing`,requiresReason:!1,description:`Being examined now.`},{id:`resolved`,label:`Resolved`,requiresReason:!1,description:`Fixed, by a change to the model.`},{id:`accepted`,label:`Accepted`,requiresReason:!1,description:`Examined and accepted as it stands.`},{id:`waived`,label:`Waived`,requiresReason:!0,description:`Examined and set aside. Needs a reason.`}]);function Hv(e){return Vv.find(t=>t.id===e)??null}function Uv(e){return Vv.some(t=>t.id===e)}function Wv({status:e,comment:t}){if(!Uv(e))return`Unknown review status ${JSON.stringify(e)}.`;let n=Hv(e);return n.requiresReason&&!String(t??``).trim()?`${n.label} needs a reason. A waiver that cannot say what it waived is not a record.`:null}var Gv=`:`,Kv=`%3A`;function qv(e,{fieldId:t=null,component:n=null,resultStateId:r=null}={}){let i=e?.objectId??``;if(!i)return null;let a=[r,t,n,i];return a.some(e=>e==null)?null:`finding${Gv}${a.map(Jv).join(Gv)}`}function Jv(e){return String(e).replaceAll(Gv,Kv)}function Yv(e){return String(e).replaceAll(Kv,Gv)}function Xv(e,{fieldId:t=null,component:n=null,resultStateId:r=null,loadCase:i=null,unit:a=null,object_id:o=null}={}){return{object_id:o??e?.objectId??null,element_id:e?.elementId??null,subpoint_index:e?.subpointIndex??null,row_index:e?.rowIndex??null,field:t,component:n,result_state_id:r,load_case:i,value:e?.value??null,unit:a??e?.unit??null,utilization:e?.utilization??null}}function Zv(e){if(typeof e!=`string`||!e.startsWith(`finding${Gv}`))return null;let t=e.slice(`finding${Gv}`.length).split(Gv);if(t.length<4)return null;let[n,r,i,...a]=t;return Xv(null,{resultStateId:Yv(n),fieldId:Yv(r),component:Yv(i),object_id:a.map(Yv).join(Gv)})}function Qv(e,t){let n=t?.subjectId??t?.issueId;if(!n)return e;let r=e.reviewDispositions?.[n]??{},i=t.status??r.status??`open`,a=t.comment??r.comment??``;if(Wv({status:i,comment:a}))return e;let o=t.at??null,s=t.author??r.author??null,c={status:i,comment:a,author:s,at:o},l=sy(r).at(-1);return l&&cy(l,c)?e:{...e,reviewDispositions:{...e.reviewDispositions??{},[n]:{...r,...t.address?{address:t.address}:r.address?{address:r.address}:{},status:i,comment:a,author:s,at:o,transitions:[...sy(r),c]}}}}function $v(e,t){let n=e.reviewDispositions?.[t];return n?{subjectId:t,status:n.status??`open`,comment:n.comment??``,author:n.author??null,at:n.at??null,address:n.address??null,transitions:sy(n)}:null}function ey(e){let t=Object.fromEntries(Vv.map(e=>[e.id,0])),n=0;for(let r of Object.values(e.reviewDispositions??{})){let e=r?.status;e in t&&(t[e]+=1,n+=1)}return{...t,touched:n}}function ty(e,{scene:t=null,at:n=null}={}){let r=new Map((e.issues??[]).map(e=>[e.id,e])),i=Object.entries(e.reviewDispositions??{}).filter(([e,t])=>e&&t&&sy(t).length>0).map(([t,n])=>ny(t,n,r.get(t),e)).sort((e,t)=>(t.recorded_at??``).localeCompare(e.recorded_at??``));return{schema:Bv,author:e.reviewerName??null,author_is_self_declared:!0,generated_at:n,scene_id:t?.id??e.sceneId??null,model_id:t?.id??null,load_case:e.activeLoadCase??null,result_state_id:e.activeResultStateId??null,dispositions:i,summary:ey(e)}}function ny(e,t,n,r){let i=sy(t),a=i.at(-1),o=e.startsWith(`finding:`),s=t.address??(o?Zv(e):null);return{subject_kind:o?`finding`:`issue`,subject_id:e,type:n?.type??null,title:n?.title??ry(s),severity:n?.severity??null,status:a?.status??t.status??`open`,comment:a?.comment??t.comment??``,author:a?.author??t.author??null,recorded_at:a?.at??t.at??null,transition_count:i.length,entity_refs:n?.entity_refs??[],address:s,transitions:i}}function ry(e){if(!e)return null;let t=e.element_id??e.object_id??`unknown element`,n=[e.field,e.component].filter(Boolean).join(` / `),r=e.load_case??e.result_state_id??`unknown case`;return`${t}${n?` — ${n}`:``} (${r})`}var iy=Object.freeze([`subject_kind`,`subject_id`,`type`,`title`,`severity`,`status`,`comment`,`author`,`recorded_at`,`transition_count`,`entity_refs`,`address`]);function ay(e){return e?[iy.join(`,`),...(e.dispositions??[]).map(e=>iy.map(t=>oy(e[t])).join(`,`))].join(`
`):``}function oy(e){if(e==null)return``;if(Array.isArray(e)||e&&typeof e==`object`)return oy(JSON.stringify(e));let t=String(e);return/[",\r\n]/.test(t)?`"${t.replaceAll(`"`,`""`)}"`:t}function sy(e){return Array.isArray(e?.transitions)?e.transitions:[]}function cy(e,t){return e.status===t.status&&(e.comment??``)===(t.comment??``)&&(e.author??null)===(t.author??null)}var ly=Object.freeze([{id:`N`,label:`N — axial force`,unit:`N`,index:0},{id:`VY`,label:`VY — shear, local y`,unit:`N`,index:1},{id:`VZ`,label:`VZ — shear, local z`,unit:`N`,index:2},{id:`MT`,label:`MT — torsion`,unit:`N·m`,index:3},{id:`MFY`,label:`MFY — bending about local y`,unit:`N·m`,index:4},{id:`MFZ`,label:`MFZ — bending about local z`,unit:`N·m`,index:5}]);function uy(e){let t=(e.objects??[]).filter(t=>fy(e,t)),n=new Map;for(let e of t)for(let t of e.metadata?.nodes??[])n.has(t)||n.set(t,[]),n.get(t).push(e);let r=new Set(t.map(e=>e.id)),i=[];for(;r.size>0;){let e=py(t,n,[...r].find(e=>(t.find(t=>t.id===e).metadata?.nodes??[]).some(e=>(n.get(e)??[]).length<2))??r.values().next().value,r);e.length>=2&&i.push({id:my(e),elementIds:e.map(e=>e.id),label:hy(e)})}return i}function dy(e,t){return uy(e).find(e=>e.elementIds.includes(t))??null}function fy(e,t){if(t?.kind!==`pipe`&&!String(t?.metadata?.element_type??``).startsWith(`pipe`)||t.metadata?.display_geometry)return!1;let n=t.metadata?.nodes;return Array.isArray(n)&&n.length===2&&n.every(e=>typeof e==`string`)}function py(e,t,n,r){let i=[],a=e.find(e=>e.id===n)??null,o=null;for(;a;){r.delete(a.id),i.push(a);let[e,n]=a.metadata.nodes,s=o===null?(t.get(e)?.length??0)>=(t.get(n)?.length??0)?e:n:e===o?n:e,c=(t.get(s)??[]).find(e=>r.has(e.id));o=s,a=c??null}return i}function my(e){return`run:${e[0].metadata.nodes[0]}->${e[e.length-1].metadata.nodes[1]}`}function hy(e){let t=e[0].name??e[0].id,n=e[e.length-1].name??e[e.length-1].id;return t===n?`${t} (${e.length} elements)`:`${t} to ${n} · ${e.length} elements`}function gy(e,t){let n=[],r=[],i={},a={},o=0;for(let[s,c]of t.elementIds.entries()){let t=Sy(e,(e.objects??[]).find(e=>e.id===c));if(!t||t.length<2)return null;s>0&&(o=r[r.length-1]??0,n.pop()),i[c]=r.length;for(let[e,i]of t.entries())e>0&&(o+=Cy(n[n.length-1],i)),n.push(i),r.push(o);a[c]=r.length-1}return{stations:r,points:n,elementStartStations:i,elementEndStations:a,totalLength:r[r.length-1]??0,elementIds:t.elementIds}}function _y(e,t,n,r=null){let i=ly.find(e=>e.id===n)??null;if(!i||!t)return null;let a=gy(e,t);if(!a)return null;let o=(r??yy(e))?.data?.element_results??{},s=[],c=0;for(let e of t.elementIds){let t=o[e],n=t?.forces_n1,r=t?.forces_n2;if(!Array.isArray(n)||!Array.isArray(r)){c+=1;continue}let l=Number(n[i.index]),u=Number(r[i.index]);if(!Number.isFinite(l)||!Number.isFinite(u)){c+=1;continue}let d=a.elementStartStations?.[e],f=a.elementEndStations?.[e];if(d===void 0||f===void 0){c+=1;continue}s.push({station:a.stations[d],value:l,elementId:e,end:`n1`}),s.push({station:a.stations[f],value:u,elementId:e,end:`n2`})}if(s.length<2)return null;s.sort((e,t)=>e.station-t.station);let l=s.map(e=>e.value);return{run:t,component:i,unit:i.unit,points:s,missing:c,extent:{station:{min:a.stations[0],max:a.totalLength},value:{min:Math.min(0,...l),max:Math.max(0,...l)}}}}function vy(e,t){let n=yy(e);if(!n)return[];let r=new Set;for(let e of t?.elementIds??[])for(let t of ly){let i=n.data?.element_results?.[e];Array.isArray(i?.forces_n1)&&Array.isArray(i?.forces_n2)&&r.add(t.id)}return ly.filter(e=>r.has(e.id))}function yy(e){return(e.overlays??[]).find(t=>!(t.kind!==`solver_result`||t.data?.result_type!==`internal_forces`||e.activeResultStateId&&t.data?.result_state_id&&t.data.result_state_id!==e.activeResultStateId||e.activeLoadCase&&t.data?.load_case&&t.data.load_case!==e.activeLoadCase))??null}function by(e,t={}){if(!e)return``;let n=Math.max(Number(t.width)||640,240),r=Math.max(Number(t.height)||200,120),i={top:12,right:12,bottom:30,left:62},a=Math.max(n-i.left-i.right,1),o=Math.max(r-i.top-i.bottom,1),{station:s,value:c}=e.extent,l=Math.max(s.max-s.min,1e-9),u=Math.max(c.max-c.min,1e-9),d=e=>i.left+(e-s.min)/l*a,f=e=>i.top+(1-(e-c.min)/u)*o,p=e.points.map((e,t)=>`${t===0?`M`:`L`}${d(e.station).toFixed(2)} ${f(e.value).toFixed(2)}`).join(` `),m=xy(c.min,c.max),h=`${e.component.label} along ${e.run.label}. Station ${wy(s.min)} to ${wy(s.max)} metres, peak ${Ty(Math.max(Math.abs(c.min),Math.abs(c.max)),e.unit)}.`,g=e.points.map(t=>`<circle class="diagram-ordinate" cx="${d(t.station).toFixed(2)}" cy="${f(t.value).toFixed(2)}" r="2.4"><title>${Ey(`${t.elementId} ${t.end} at ${wy(t.station)} m: ${Ty(t.value,e.unit)}`)}</title></circle>`).join(``);return[`<svg class="station-diagram" viewBox="0 0 ${n} ${r}" role="img" aria-label="${Ey(h)}" preserveAspectRatio="none">`,`<line class="diagram-zero" x1="${i.left}" y1="${f(0).toFixed(2)}" x2="${(n-i.right).toFixed(2)}" y2="${f(0).toFixed(2)}" />`,...m.map(t=>[`<line class="diagram-grid" x1="${i.left}" y1="${f(t).toFixed(2)}" x2="${(n-i.right).toFixed(2)}" y2="${f(t).toFixed(2)}" />`,`<text class="diagram-tick" x="${i.left-6}" y="${(f(t)+3).toFixed(2)}" text-anchor="end">${Ey(Ty(t,e.unit))}</text>`].join(``)),`<line class="diagram-grid" x1="${i.left}" y1="${(i.top+o).toFixed(2)}" x2="${(n-i.right).toFixed(2)}" y2="${(i.top+o).toFixed(2)}" />`,`<path class="diagram-path" d="${p}" />`,g,`<text class="diagram-axis" x="${(i.left+a/2).toFixed(2)}" y="${(r-6).toFixed(2)}" text-anchor="middle">Station along run (m)</text>`,`</svg>`].join(``)}function xy(e,t){let n=t-e;if(!(n>0))return[e];let r=n/4,i=10**Math.floor(Math.log10(r)),a=r/i,o=(a<=1?1:a<=2?2:a<=5?5:10)*i,s=[];for(let n=Math.ceil(e/o)*o;n<=t+o*1e-9;n+=o)s.push(Number(n.toPrecision(12)));return s.length>0?s:[e,t]}function Sy(e,t){let n=(e.geometryAssets??[]).find(e=>e.id===t?.geometry_asset_id)?.generation_config?.points;if(!Array.isArray(n)||n.length<2)return null;let r=n.map(e=>[Number(e?.[0]),Number(e?.[1]),Number(e?.[2])]).filter(e=>e.every(Number.isFinite));return r.length>=2?r:null}function Cy(e,t){return Math.hypot(e[0]-t[0],e[1]-t[1],e[2]-t[2])}function wy(e){return Number(e.toPrecision(4)).toString()}function Ty(e,t){return`${Number(e.toPrecision(4))} ${t}`}function Ey(e){return String(e).replaceAll(`&`,`&amp;`).replaceAll(`<`,`&lt;`).replaceAll(`>`,`&gt;`).replaceAll(`"`,`&quot;`)}var Dy=Object.freeze([0,0,0]),Oy=(e,t)=>[e[1]*t[2]-e[2]*t[1],e[2]*t[0]-e[0]*t[2],e[0]*t[1]-e[1]*t[0]],ky=.01;function Ay(e,t=ky){return Number.isFinite(e)&&e<=t}function jy(e,t){let n=t?.reactionForce??null,r=t?.reactionMoment??null;if(!n&&!r)return null;let i=t?.loadCaseDefinition??null,a=Fy(e,t?.loadCase??null),o=Ry(a.forces.map(e=>e.components)),s=Ry([...a.moments.map(e=>e.components),...a.forces.map(e=>Oy(e.position??Dy,e.components))]),c=Ry(n?Object.values(n):[]),l=Ry(r?Object.values(r):[]),u=zy(c,o),d=zy(l,s),f=Hy(Object.values(n??{}))+Hy(a.forces.map(e=>e.components)),p=Hy(Object.values(r??{}))+Hy([...a.moments.map(e=>e.components),...a.forces.map(e=>Oy(e.position??Dy,e.components))]),m=Ly(i);return{loadCase:t?.loadCase??null,complete:m.length===0,omitted:m,included:[`${Vy(n??r)} support reaction${Vy(n??r)===1?``:`s`}`,...a.total>0?[`${a.total} authored nodal load${a.total===1?``:`s`}`]:[]],reactionForce:c,reactionMoment:l,appliedForce:o,appliedMomentAboutOrigin:s,residualForce:u,residualMoment:d,forceResidual:Uy(u),momentResidual:Uy(d),forceResidualRatio:Wy(Uy(u),f),momentResidualRatio:Wy(Uy(d),p),tolerance:ky}}function My(e,t){let n=t?.fieldId?(e.resultFields??[]).find(e=>e.id===t.fieldId):null,r=(t?.overlay??null)?.data??{},i=Gy(r.derivation,r.averaging);if(i)return i;let a=n?.support??Py(t?.fieldId);return a===`subpoint`?Gy(r.stress_basis,`measured at each Code_Aster section point (${r.component??`VMIS`} from ${r.field??`SIEQ_ELNO`}); the wall between points is interpolated`):Ny(r.field,t?.field)?`element maximum of the two element-end values`:a===`node`?`nodal value read from the solver result table`:a===`cell`?`one value per element, as reported by the solver`:null}function Ny(e,t){return String(e??``).toLowerCase()===`max_von_mises`||String(t??``).toLowerCase().startsWith(`fe vmis`)}function Py(e){return typeof e==`string`?e.includes(`tuyau_subpoints`)||e.includes(`subpoint`)?`subpoint`:e.includes(`displacement`)||e.includes(`reaction`)?`node`:`cell`:null}function Fy(e,t){let n=[],r=[];for(let i of e.objects??[]){if(i.kind!==`applied_load`)continue;let a=i.metadata??{};if(t&&a.load_case&&a.load_case!==t)continue;let o=By(a.components);if(!o)continue;let s={components:o,position:Iy(e,a.node_id)};a.vector_kind===`moment`?r.push(s):n.push(s)}return{forces:n,moments:r,total:n.length+r.length}}function Iy(e,t){if(!t)return null;for(let n of e.overlays??[])for(let e of n.data?.vectors??[])if(e.node_id===t&&Array.isArray(e.start)){let t=By(e.start);if(t)return t}return null}function Ly(e){if(!e)return[`load definition not in this bundle`];let t=[];return e.gravity&&t.push(`self-weight (assembled inside Code_Aster)`),Number(e.internal_pressure_pa)>0&&t.push(`internal pressure (assembled inside Code_Aster)`),(e.pressure_fields??[]).length>0&&t.push(`pressure fields (assembled inside Code_Aster)`),Number(e.line_load_count)>0&&t.push(`line loads (assembled inside Code_Aster)`),(e.field_count??0)>0&&t.push(`authored load fields (assembled inside Code_Aster)`),t}function Ry(e){return e.reduce((e,t)=>zy(e,t),[...Dy])}function zy(e,t){return[e[0]+t[0],e[1]+t[1],e[2]+t[2]]}function By(e){if(!Array.isArray(e)||e.length<3)return null;let t=e.slice(0,3).map(Number);return t.every(e=>Number.isFinite(e))?t:null}function Vy(e){return Object.keys(e??{}).length}function Hy(e){return e.reduce((e,t)=>e+Uy(t),0)}function Uy(e){return Math.hypot(e[0],e[1],e[2])}function Wy(e,t){return t>0?e/t:null}function Gy(...e){for(let t of e)if(typeof t==`string`&&t.trim())return t.trim();return null}function Ky(e){let t=e?.provenance??[],n=t.find(e=>e.solver_name)?.solver_name;if(!n)return``;let r=t.map(e=>e.metadata?.runtime_version).find(Boolean),i=new Set(t.map(e=>e.load_case).filter(Boolean));return[r?`${n} ${r}`:n,i.size>0?`${i.size} case${i.size===1?``:`s`}`:null].filter(Boolean).join(` · `)}function qy(e){let t=(t=>e?.tables?.[t]??null)(`diagnostics`);return{analysisStatus:e?.analysis_status??`Not available`,warningCount:(t?.rows??[]).filter(e=>e.severity===`warning`).length}}function Jy(e,t){if(![e,t].every(e=>Array.isArray(e)&&e.length===3&&e.every(e=>typeof e==`number`&&Number.isFinite(e))))throw TypeError(`Measurement requires two finite 3D points in metres.`);return Math.hypot(...e.map((e,n)=>e-t[n]))}function Yy(e,t,n={}){if(t=g(e,t),!e.objects.some(e=>e.id===t))return e;let r=e.selectedObjectIds??[],i=n.additive?[...r.filter(e=>e!==t),t]:[t];return{...e,selectedObjectIds:i}}function Xy(e){let t=new Set([...e.hiddenObjectIds??[],...h(e,e.selectedObjectIds??[])]);return ib({...e,hiddenObjectIds:[...t]})}function Zy(e){return ib({...e,isolatedObjectIds:h(e,e.selectedObjectIds??[])})}function Qy(e){return ib({...e,hiddenObjectIds:[],isolatedObjectIds:[],sectionBox:void 0})}function $y(e,t){let n=e.objects.find(e=>e.id===t);if(!n)return[];let r=e.geometryAssets.find(e=>e.id===n.geometry_asset_id),i={...n.metadata?.attributes??{}};n.metadata?.insulation?.id&&(i.insulation=n.metadata.insulation.id,i.insulation_material=n.metadata.insulation.material,i.insulation_thickness_m=n.metadata.insulation.thickness_m);let a=ob(e,n),o=sb(n),s=cb(e,n),c=lb(n),l=ub(n,r),u=n.metadata?.profile??{},d=n.metadata?.property_lines??{},f=d.attributes??{};return[{id:`identity`,title:`Identity`,rows:ab({id:n.id,entity_ref:n.entity_ref,kind:n.kind,name:n.name})},{id:`geometry`,title:`Geometry`,rows:ab({geometry_asset_id:n.geometry_asset_id,asset_format:r?.format,bounds:r?.bounds})},{id:`attributes`,title:`Attributes`,rows:ab({section:n.metadata?.section,material:n.metadata?.material,...i}),sourceLines:ab({section:d.section,material:d.material,...f,insulation_material:f.insulation,insulation_thickness_m:f.insulation})},{id:`profile`,title:`Profile`,rows:ab(u),sourceLine:d.section},{id:`physical`,title:`Physical`,rows:ab(n.physical??{})},{id:`quantities`,title:`Quantities`,rows:ab(n.quantities??{})},{id:`result_values`,title:`Result Values`,rows:ab(a)},{id:`clash`,title:`Clash`,rows:ab(o)},{id:`issues`,title:`Issues`,rows:ab(s)},{id:`external_refs`,title:`External Refs`,rows:ab(c)},{id:`ifc`,title:`IFC reference`,rows:ab({guid:n.source?.ifc_guid,class:n.metadata?.ifc_class,reference:n.source?.reference_id,...Object.fromEntries(Object.entries(n.metadata?.properties??{}).flatMap(([e,t])=>Object.entries(t??{}).map(([t,n])=>[`${e}.${t}`,String(n)])))})},{id:`provenance`,title:`Provenance`,rows:ab(l)}].filter(e=>Object.keys(e.rows).length>0)}function eb(e,t={}){let n=new Set(e.visibleObjectIds??e.objects.map(e=>e.id)),r=h(e,e.selectedObjectIds??[]).filter(e=>n.has(e)),i=new Set(r.length?r:e.selectedObjectIds??[]),a=new Set(e.objects.filter(e=>i.has(e.id)).map(e=>e.geometry_asset_id).filter(Boolean)),o=e.geometryAssets.filter(e=>a.has(e.id)||(e.object_ids??[]).some(e=>i.has(e))).map(e=>e.bounds).filter(e=>Array.isArray(e)&&e.length===6);if(o.length===0)return e;let s=tb(db(o),Number(t.maxSpan))??db(o),c=[(s[0]+s[3])/2,(s[1]+s[4])/2,(s[2]+s[5])/2],l=Math.max(Math.hypot(s[3]-s[0],s[4]-s[1],s[5]-s[2]),1),u=Number(e.camera?.fitRequest?.id??0)+1;return{...e,camera:{...e.camera,target:c,distance:l,fitRequest:{id:u,bounds:s}}}}function tb(e,t){if(!Number.isFinite(t)||t<=0)return null;let n=[0,1,2].map(t=>(e[t]+e[t+3])/2),r=[...n,...n],i=!1;for(let a=0;a<3;a+=1)e[a+3]-e[a]>t&&(r[a]=n[a]-t/2,r[a+3]=n[a]+t/2,i=!0);return i?r:null}function nb(e,t=.15,n=.5){let r=e.bounds;if(!Array.isArray(r)||r.length!==6)return null;let i=Math.hypot(r[3]-r[0],r[4]-r[1],r[5]-r[2]);return!Number.isFinite(i)||i<=0?null:Math.max(i*t,n)}function rb(e,t){let n=Yy(e,t);return n===e?e:eb(n,{maxSpan:nb(e)})}function ib(e){return{...e,visibleObjectIds:Zn(e)}}function ab(e){return Object.fromEntries(Object.entries(e).filter(([e,t])=>t!=null&&t!==``))}function ob(e,t){let n={};for(let r of e.overlays??[]){if(![`solver_result`,`result_state`].includes(r.kind))continue;let e=r.data??{},i=e.field||e.result_type||r.name||r.id;e.values?.[t.id]!==void 0&&(n[i]=e.values[t.id],e.unit&&(n[`${i}_unit`]=e.unit)),e.element_results?.[t.id]&&Object.assign(n,e.element_results[t.id])}return n}function sb(e){let t=e.metadata??{},n=t.review??{},r=t.clash??t.clash_metadata??{};return{left:t.left??r.left??n.object_pair?.[0],right:t.right??r.right??n.object_pair?.[1],distance_m:t.distance_m??r.distance_m,penetration_m:t.penetration_m??r.penetration_m,cold_distance_m:t.cold_distance_m??r.cold_distance_m,operating_distance_m:t.operating_distance_m??r.operating_distance_m,envelope_type:t.envelope_type??r.envelope_type??n.envelope_type}}function cb(e,t){return{issue_ids:(e.issues??[]).filter(e=>(e.object_ids??[]).includes(t.id)||(e.entity_refs??[]).includes(t.entity_ref)||e.id===t.metadata?.issue_id).map(e=>e.id).join(`, `)}}function lb(e){return{...e.external_refs??{},...e.metadata?.external_refs??{},ifc_guid:e.ifc_guid??e.metadata?.ifc_guid??e.external_refs?.ifc_guid??e.metadata?.external_refs?.ifc_guid}}function ub(e,t){return{source_ref:e.metadata?.source_ref??t?.generation_config?.source_ref??t?.generation_config?.entity_ref,source:e.metadata?.source??t?.generation_config?.source,role:e.metadata?.role??t?.generation_config?.role,mesh_id:e.metadata?.mesh_id??e.source?.analysis_mesh?.id??t?.generation_config?.mesh_id,member_type:e.source?.analysis_mesh?.member_type,member_id:e.source?.analysis_mesh?.member_id}}function db(e){let t=[1/0,1/0,1/0],n=[-1/0,-1/0,-1/0];for(let r of e)for(let e=0;e<3;e+=1)t[e]=Math.min(t[e],r[e]),n[e]=Math.max(n[e],r[e+3]);return[...t,...n]}var fb,pb;function mb(e,t){pb?.cancel();let n,r,i=!1,a={promise:new Promise((a,o)=>{let s=(e,t)=>{i||(i=!0,clearTimeout(r),fb&&(fb.onmessage=fb.onerror=null),e&&(fb?.terminate(),fb=null),pb=null,e?o(e):a(t))};n=e=>s(e);try{fb??=new Worker(new URL(``+new URL(`browserPython.worker-l7VIOxsg.js`,import.meta.url).href,``+import.meta.url),{type:`module`}),r=setTimeout(()=>s(Error(`Geometry preview timed out. Shorten the script and try again.`)),12e4),fb.onerror=e=>s(Error(e.message||`The browser Python worker could not start.`)),fb.onmessage=({data:e})=>{e.status?t(e.status):e.ok?s(null,e.scene):s(Object.assign(Error(e.error),{line:e.line}))},fb.postMessage({code:e,runtimeUrl:new URL(`./tuba-browser.zip`,document.baseURI).href})}catch(e){s(e)}}),cancel:()=>n(new DOMException(`Preview stopped`,`AbortError`))};return i||(pb=a),a}function hb(e){return{scene:e,objects:e.objects,objectMap:{},overlays:e.overlays,geometryAssets:e.geometry_assets,geometryPayloads:e.geometry_assets.map(e=>({...e,asset_id:e.id})),review:null,reviewDiagnostics:[],legacyReview:!1}}var gb=Object.freeze({anchor:`Anchor`,guide:`Guide`,hanger:`Spring hanger`,rest:`Rest`,spring:`Spring hanger`}),_b=Object.freeze({analysis_mesh_element:`Mesh element`,analysis_mesh_node:`Mesh node`,clash_marker:`Clash`,displacement_vector:`Displacement`,obstacle:`Obstacle`,pipe:`Pipe`,reaction_vector:`Reaction`,route_candidate:`Route candidate`,support:`Support`,support_link:`Support attachment`}),vb=new Set([`identity`,`geometry`,`provenance`]),yb=`µ`,bb=`·`,xb=`—`;function Sb(e){let t=String(e??``);return t.charAt(0).toUpperCase()+t.slice(1).replace(/_/g,` `)}function Cb(e){return Object.fromEntries(Object.entries(e).filter(([,e])=>e!=null&&e!==``))}function wb(e){let t=e?.bounds;if(!Array.isArray(t)||t.length!==6)return null;let n=[0,1,2].map(e=>(Number(t[e])+Number(t[e+3]))/2);return n.every(Number.isFinite)?n:null}function Tb(e,t){return{...t?.generation_config??{},...e.metadata??{}}}function Eb(e,t){let n=e?.[t];if(!Array.isArray(n)||n.length!==3)return null;let r=n.map(Number);return r.every(Number.isFinite)?r:null}function Db(e,t){return Og.filter((n,r)=>e[r]===t)}var Ob=e=>Number(e),kb=e=>Number.isFinite(Ob(e))&&Ob(e)>0,Ab=e=>Number.isFinite(Ob(e))&&Ob(e)!==0;function jb(e,t,n){let r=n?` at node ${n}`:``,i=e.attached_to?` Acts against node ${e.attached_to}.`:` Anchored to ground.`,a=Db(t,`fixed`),o=Db(t,`one-way`),s=Db(t,`spring`);if(a.length===Og.length)return`Fixes all six degrees of freedom${r}.${i}`;if(o.length>0){let t=[];Ab(e.gap)&&t.push(`${N(e.gap,`m`,`engineering`)} gap`),kb(e.friction_coefficient)&&t.push(`friction ${yb} ${oe(e.friction_coefficient)}`);let n=t.length>0?` ${Sb(t.join(`, `))}.`:``;return`Carries compression only along ${o.join(` and `)} and lifts off in tension.${n}${i}`}if(s.length>0&&a.length===0)return`Spring on ${s.join(` and `)}${r}. Carries no rigid restraint ${xb} the solver adds a discrete spring element.${i}`;if(a.length===0)return`Holds no degree of freedom${r}.${i}`;let c=Db(t,`free`).filter(e=>!e.startsWith(`R`)),l=Db(t,`free`).filter(e=>e.startsWith(`R`)).length===3,u=[`Holds ${a.join(` and `)}${r}.`];return c.length>0?u.push(`${c.join(` and `)} ${c.length===1?`runs`:`run`} free${l?`, as do all three rotations`:``}.`):l&&u.push(`All three rotations run free.`),u.push(i.trim()),u.join(` `)}function Mb(e,t,n){let r=[],i=(e,t)=>r.push({kind:`row`,label:e,value:t});if(e.attached_to){let t=Array.isArray(e.attached_to_groups)?e.attached_to_groups.filter(Boolean):[];i(`Restrained to`,t.length>0?`${e.attached_to} (${t.join(`, `)})`:String(e.attached_to))}else i(`Restrained to`,`Ground`);let a=Eb(e,`direction`);a&&i(`Direction`,`[${a.map(e=>oe(e)).join(`, `)}]`);let o=Array.isArray(e.stiffness_matrix)?e.stiffness_matrix.map(Number):[];o.forEach((e,t)=>{!Number.isFinite(e)||e===0||i(`Stiffness K${Og[t].toLowerCase()}`,N(e,t<3?`N`:`N*m`,n))}),o.length===0&&Ab(e.stiffness)&&i(`Stiffness`,N(e.stiffness,`N`,n)),Ab(e.gap)&&i(`Gap`,N(e.gap,`m`,n)),kb(e.friction_coefficient)&&i(`Friction`,`${yb} ${oe(e.friction_coefficient)}`),kb(e.mass)&&i(`Mass`,`${oe(e.mass)} kg`);let s=Eb(e,`imposed_displacement`);if(s){i(`Imposed displacement`,s.map(e=>N(e,`m`,n)).join(`, `));let t=(Array.isArray(e.spring_stiffness)?e.spring_stiffness:[]).map(Number).filter(e=>Number.isFinite(e)&&e!==0);t.length&&i(`Prescribed by penalty spring`,`${oe(M(t[0],`N`,n)/(M(1,`m`,n)||1))} ${j(`N`,n)} / ${j(`m`,n)}`)}let c=(t.objects??[]).filter(t=>{let n=t.metadata?.nodes??[t.metadata?.n1,t.metadata?.n2];return Array.isArray(n)&&n.includes(e.node)}).map(e=>e.name).filter(Boolean);return c.length>0&&i(`On element`,c.join(`, `)),r.length>0?[{title:`Definition`,lines:r}]:[]}var Nb=Object.freeze([{resultType:`reaction_force`,key:`reaction_force_n`,unit:`N`,label:`Force`,axes:[`Fx`,`Fy`,`Fz`]},{resultType:`reaction_moment`,key:`reaction_moment_nm`,unit:`N*m`,label:`Moment`,axes:[`Mx`,`My`,`Mz`]},{resultType:`displacement`,key:`displacement_m`,unit:`m`,label:`Displacement`,axes:[`Ux`,`Uy`,`Uz`]}]);function Pb(e,t,n){let r=t?.generation_config??{},i=Nb.find(e=>e.resultType===r.result_type),a=i?Eb(r,i.key):null;if(!i||!a)return[];let o=[{kind:`row`,label:`Magnitude`,value:N(Math.hypot(...a),i.unit,n)},{kind:`row`,label:i.axes.join(` / `),value:`${a.map(e=>oe(M(e,i.unit,n))).join(` / `)} ${j(i.unit,n)}`}];return r.node_id&&o.push({kind:`row`,label:`Node`,value:r.node_id}),r.load_case&&o.push({kind:`row`,label:`Load case`,value:r.load_case}),[{title:i.label,lines:o}]}function Fb(e,t,n){if(!t)return[];let r=vt(e),i=r?.overlay?.data?.result_state_id,a=[];for(let{resultType:r,key:o,unit:s,label:c,axes:l}of Nb){let u=Eb((e.geometryAssets??[]).find(e=>{let n=e.generation_config??{};return n.source===`tuba.result_state`&&n.result_type===r&&n.node_id===t&&(!i||n.result_state_id===i)})?.generation_config,o);u&&(a.push({kind:`row`,label:c,value:N(Math.hypot(...u),s,n)}),a.push({kind:`row`,label:l.join(` / `),value:`${u.map(e=>oe(M(e,s,n))).join(` / `)} ${j(s,n)}`}))}if(a.length===0)return[];let o=r?.overlay?.data?.load_case;return[{title:o?`Reactions ${bb} ${o}`:`Reactions`,lines:a}]}function Ib(e,t,n){let r=Et(e);if(!r)return[];let i=Ot(e),a=Number(i[t.id]);if(!Number.isFinite(a))return[];let o=Object.values(i).map(Number).filter(Number.isFinite),s=o.filter(e=>e>a).length+1,c=[{kind:`row`,label:r.field,value:N(a,r.unit,n)}];o.length>1&&c.push({kind:`row`,label:`Rank`,value:`${s} of ${o.length}${s===1?` ${bb} peak`:``}`});let l=Number(r.overlay?.data?.utilization_values?.[t.id]);Number.isFinite(l)&&c.push({kind:`row`,label:`Utilisation`,value:oe(l)});let u=r.loadCase??r.overlay?.data?.load_case;return[{title:u?`Probe ${bb} ${u}`:`Probe`,lines:c}]}function Lb(e,t,n){let r=Object.values(mn(e)).find(e=>`support:${e.support_id}`===t.entity_ref||e.support_id===t.metadata?.support_id||e.support_id===t.name);if(!r)return{section:null,badge:null};let i=e=>Math.hypot(...e);return{section:{title:`Contact`,lines:[{kind:`row`,label:`Status`,value:r.status},{kind:`row`,label:`Normal force`,value:N(r.normal_force,`N`,n)},{kind:`row`,label:`Friction limit`,value:N(r.friction_limit,`N`,n)},{kind:`row`,label:`|Ft|`,value:N(i(r.tangential_force),`N`,n)},...r.utilization===null?[]:[{kind:`row`,label:`Utilisation`,value:oe(r.utilization)}],{kind:`row`,label:`Slip`,value:N(i(r.slip),`m`,n)}]},badge:r.status}}function Rb(e,t){let n=e.metadata??{},r=Number(e.quantities?.length_m),i=Array.isArray(n.nodes)?n.nodes:[n.n1,n.n2].filter(Boolean),a=[[n.section,n.material].filter(Boolean).join(` `),[Number.isFinite(r)?N(r,`m`,t):null,i.length===2?`from ${i[0]} to ${i[1]}`:null].filter(Boolean).join(` `)].filter(Boolean).join(`, `);return a?`${a}.`:``}function zb(e,t){let n=e.metadata??{},r=n.clash??n.clash_metadata??{},i=n.left??r.left,a=n.right??r.right,o=Number(n.penetration_m??r.penetration_m);return!i||!a?``:`${i} overlaps ${a}${Number.isFinite(o)&&o>0?` by ${N(o,`m`,t)}`:``}.`}function Bb(e){let t=e.metadata??{};if(e.kind!==`applied_load`||!t.load_case)return[];let n=t.property_lines?.load_case,r=[{kind:`row`,label:`Load case`,value:t.load_case,...n?{sourceLine:n}:{}}];return t.vector_kind===`line_load`&&(r.push({kind:`row`,label:`Kind`,value:`Distributed line load`}),t.value_npm!=null&&r.push({kind:`row`,label:`Intensity`,value:`${t.value_npm} N/m`}),t.direction&&r.push({kind:`row`,label:`Direction`,value:`[${t.direction.join(`, `)}]`}),t.element_id&&r.push({kind:`row`,label:`Element`,value:t.element_id}),t.route_id&&r.push({kind:`row`,label:`Route`,value:t.route_id})),[{title:`Load`,lines:r}]}function Vb(e){let t=e.metadata??{},n=t.node??`?`,r=t.attached_to??`?`,i=Array.isArray(t.attached_to_groups)?t.attached_to_groups.filter(Boolean):[];return`Links node ${n} to ${i.length>0?`${r} (${i.join(`, `)})`:r}.`}function Hb(e,t){let n=(e.objects??[]).find(e=>e.id===t);if(!n)return null;let r=(e.geometryAssets??[]).find(e=>e.id===n.geometry_asset_id),i=O(e),a=n.kind===`support`,o=a?Tb(n,r):{},s=a?o.node:void 0,c=a?Rg(o):null,l=a?Lb(e,n,i):{section:null,badge:null},u=wb(r),d=$y(e,t).filter(e=>!vb.has(e.id)).map(e=>({title:e.title,...e.sourceLine?{sourceLine:e.sourceLine}:{},lines:Object.entries(e.rows).map(([t,n])=>({kind:`row`,label:t,value:n,...e.sourceLines?.[t]?{sourceLine:e.sourceLines[t]}:{}}))}));return{objectId:n.id,title:a?gb[String(o.support_type??``).toLowerCase()]??Sb(o.support_type??`Support`):_b[n.kind]??Sb(n.kind??`Object`),badge:l.badge,lede:a?jb(o,c,s):n.kind===`support_link`?Vb(n):n.kind===`clash_marker`?zb(n,i):Rb(n,i),meta:[n.name,s?`node ${s}`:null,u?`${u.map(e=>oe(e)).join(`, `)} m`:null].filter(Boolean).join(` ${bb} `),dofs:c?Og.map((e,t)=>({axis:e,state:c[t]})):null,restraintLine:a?n.metadata?.property_lines?.restraint:void 0,sections:a?[...Ib(e,n,i),...Mb(o,e,i),...Fb(e,s,i),...l.section?[l.section]:[],...d]:[...Ib(e,n,i),...Pb(n,r,i),...Bb(n),...d],reference:Cb({entity_ref:n.entity_ref,geometry:r?.format,source:n.metadata?.source??r?.generation_config?.source})}}function Ub(e,t){switch(t.type){case`selectObjects`:return Gb({...e,selectedObjectIds:Kb(e,t.objectIds??[])});case`selectObject`:return Yy(e,t.objectId,{additive:t.additive});case`hideSelected`:return Xy(e);case`isolateSelection`:return Zy(e);case`fitSelection`:return eb(e,{maxSpan:t.maxSpan});case`restoreVisibility`:return Qy(e);case`applySectionBox`:return hi(e,t.sectionBox);case`restoreViewState`:return vi(e,t.view);case`focusIssue`:return pi(e,t.issueId);case`setLayerVisibility`:return Xn(e,t.layerId,t.visible);case`setOverlayVisibility`:return Tr(e,t.overlayId,t.visible);case`setBodyVisibility`:return Ar(e,t.bodyId,t.visible);case`setBodyOpacity`:return jr(e,t.bodyId,t.opacity);case`cycleBodyOpacity`:return Mr(e,t.bodyId);case`setUnitSystem`:return k(e,t.unitSystem);case`setModelColorBy`:return{...e,modelColorBy:t.colorBy??`default`,colorChannel:`model`};case`setColorChannel`:return{...e,colorChannel:t.colorChannel??e.colorChannel};case`setStage`:return fr({...e,stage:t.stage},t.stage);case`resetLayerVisibility`:{let t=e;for(let n of Object.values(e.layers??{}))t=Xn(t,n.id,n.defaultVisible!==!1);return Gb(t)}case`setContactNeutral`:return Gb({...e,contactNeutral:t.neutral});case`setContactArrows`:return{...e,contactArrows:{...e.contactArrows,[t.quantity]:t.visible}};case`setContactHistoryAxis`:return{...e,contactHistoryAxis:t.axis};case`setActiveResultState`:return Gb(De(Ut(e,t.resultStateId)));case`setActiveLoadCase`:return Gb(L(Ht(e,t.loadCase),t.loadCase));case`setColoringField`:return Te(e,t.fieldId);case`setColoringComponent`:return Ee(e,t.component);case`setActiveGeometryState`:return Gb(Wt(e,t.geometryStateId));case`setResultThreshold`:return Gt(e,t.threshold);case`setUtilizationThreshold`:return Kt(e,t.threshold);case`setLegendBands`:return Jt(e,t.bands,t.scaleKey);case`setLegendRange`:return Yt(e,t.range,t.scaleKey);case`resetLegendScale`:return Xt(e,t.scaleKey);case`setActiveFinding`:return Zt(e,t.objectId);case`focusFinding`:return rb(e,t.objectId);case`setRunDiagramRun`:return{...e,runDiagramRunId:t.runId??null};case`setRunDiagramComponent`:return{...e,runDiagramComponent:t.component??null};case`setDisplacementVectorScale`:return Qt(e,`displacement`,t.scale);case`setReactionVectorScale`:return Qt(e,`reaction`,t.scale);case`setMomentVectorScale`:return Qt(e,`moment`,t.scale);case`setVisualDeformationScale`:return Gb($t(e,t.scale));case`setIssueReviewStatus`:return Qv(e,{issueId:t.issueId,status:t.status,author:e.reviewerName??null,at:t.at??null});case`setIssueReviewComment`:return Qv(e,{issueId:t.issueId,comment:t.comment??``,author:e.reviewerName??null,at:t.at??null});case`recordDisposition`:return Qv(e,{...t,author:t.author??e.reviewerName??null});case`setReviewerName`:return{...e,reviewerName:String(t.name??``).trim()||null};default:return e}}function Wb(e,t,{reviewDefaultColor:n=!1}={}){let r=new Set(t.objects.map(e=>e.id)),i={...t.layers};for(let[t,n]of Object.entries(e.layers??{}))i[t]&&(i[t]={...i[t],visible:n.visible});let a=(t.overlays??[]).map(t=>{let n=(e.overlays??[]).find(e=>e.id===t.id);if(n)return{...t,visible:n.visible};let r=i[`overlay:${t.kind||`overlay`}`];return r?{...t,visible:r.visible}:t}),o=new Set((t.geometryStates??[]).map(e=>e.data?.id??e.id)),s=ht(e,t),c=o.has(e.activeGeometryStateId)?e.activeGeometryStateId:t.activeGeometryStateId,l=Ht({...t,activeResultStateId:s.activeResultStateId,activeGeometryStateId:c},s.activeLoadCase);return Pr(Gb(De({...t,layers:i,overlays:a,camera:e.camera??t.camera,selectedObjectIds:(e.selectedObjectIds??[]).filter(e=>r.has(e)),hiddenObjectIds:(e.hiddenObjectIds??[]).filter(e=>r.has(e)),isolatedObjectIds:(e.isolatedObjectIds??[]).filter(e=>r.has(e)),activeLoadCase:l.activeLoadCase,activeResultStateId:s.activeResultStateId??l.activeResultStateId,activeGeometryStateId:l.activeGeometryStateId,resultThreshold:e.resultThreshold??t.resultThreshold,resultVectorScales:e.resultVectorScales??t.resultVectorScales,utilizationThreshold:e.utilizationThreshold??t.utilizationThreshold,reviewDispositions:e.reviewDispositions??t.reviewDispositions,visualDeformationScale:e.visualDeformationScale??t.visualDeformationScale,bodyOpacity:e.bodyOpacity??t.bodyOpacity,referenceGridVisible:e.referenceGridVisible??t.referenceGridVisible,unitSystem:e.unitSystem??t.unitSystem,modelColorBy:n?t.modelColorBy:e.modelColorBy??t.modelColorBy??`default`,colorChannel:n?t.colorChannel:e.colorChannel??t.colorChannel,stage:e.stage??t.stage,coloring:n?t.coloring:e.coloring??t.coloring,visibleOverlayIds:a.filter(e=>e.visible!==!1).map(e=>e.id)})))}function Gb(e){return{...e,visibleObjectIds:Zn(e)}}function Kb(e,t){let n=new Set(e.objects.map(e=>e.id));return qb(t.filter(e=>n.has(e)))}function qb(e){return[...new Set(e)]}var Jb=Object.freeze({displacement:`setDisplacementVectorScale`,moment:`setMomentVectorScale`,reaction:`setReactionVectorScale`}),J={appShell:document.querySelector(`[data-embed]`),appHeader:document.querySelector(`[data-app-header]`),status:document.querySelector(`[data-runtime-status]`),sceneTitle:document.querySelector(`[data-scene-title]`),sceneMeta:document.querySelector(`[data-scene-meta]`),buildIdentity:document.querySelector(`[data-build-identity]`),viewerIdentity:document.querySelector(`[data-viewer-identity]`),exchangeOpen:document.querySelector(`[data-exchange-open]`),exchangeDialog:document.querySelector(`[data-exchange-dialog]`),reportLink:document.querySelector(`[data-report-link]`),statusChip:document.querySelector(`[data-status-chip]`),statusStrip:document.querySelector(`[data-status-strip]`),solverFact:document.querySelector(`[data-solver-fact]`),applicabilityFact:document.querySelector(`[data-applicability-fact]`),selectionFact:document.querySelector(`[data-selection-fact]`),stripUnits:document.querySelector(`[data-strip-units]`),taskRail:document.querySelector(`[data-task-rail]`),inspector:document.querySelector(`[data-inspector]`),reviewDrawer:document.querySelector(`[data-review-drawer]`),reviewTally:document.querySelector(`[data-review-tally]`),contactTable:document.querySelector(`[data-contact-table]`),contactDisplay:document.querySelector(`[data-contact-display]`),reactionTable:document.querySelector(`[data-reaction-table]`),runDiagram:document.querySelector(`[data-run-diagram]`),runDiagramSummary:document.querySelector(`[data-run-diagram-summary]`),runDiagramBody:document.querySelector(`[data-run-diagram-body]`),objectsSection:document.querySelector(`[data-objects-section]`),findTally:document.querySelector(`[data-find-tally]`),findScope:document.querySelector(`[data-find-scope]`),findDismiss:document.querySelector(`[data-find-dismiss]`),railUtility:document.querySelector(`[data-rail-utility]`),railPopover:document.querySelector(`[data-rail-popover]`),displayStrip:document.querySelector(`[data-display-strip]`),displayPalette:document.querySelector(`[data-display-palette]`),sectionBoxControls:document.querySelector(`[data-section-box-controls]`),bodyList:document.querySelector(`[data-body-list]`),projectionNote:document.querySelector(`[data-projection-note]`),sectionProfile:document.querySelector(`[data-section-profile]`),discretisationCheck:document.querySelector(`[data-discretisation-check]`),balanceCheck:document.querySelector(`[data-balance-check]`),viewportLegend:document.querySelector(`[data-viewport-legend]`),bodyLegend:document.querySelector(`[data-body-legend]`),bodyLegendToggle:document.querySelector(`[data-body-legend-toggle]`),layerList:document.querySelector(`[data-layer-list]`),layerTally:document.querySelector(`[data-layer-tally]`),colorBy:document.querySelector(`[data-color-by]`),colorLegend:document.querySelector(`[data-color-legend]`),resultControls:document.querySelector(`[data-result-controls]`),fieldDetails:document.querySelector(`[data-field-details]`),fieldDescription:document.querySelector(`[data-field-description]`),averagingNote:document.querySelector(`[data-averaging-note]`),referenceNote:document.querySelector(`[data-reference-note]`),envelopeNote:document.querySelector(`[data-envelope-note]`),analysisDetails:document.querySelector(`[data-analysis-details]`),analysisSummary:document.querySelector(`[data-analysis-summary]`),resultShape:document.querySelector(`[data-result-shape]`),overlaysBlock:document.querySelector(`[data-overlays-block]`),overlayList:document.querySelector(`[data-overlay-list]`),hotspotList:document.querySelector(`[data-hotspot-list]`),diagnosticList:document.querySelector(`[data-diagnostic-list]`),searchInput:document.querySelector(`[data-search]`),issueList:document.querySelector(`[data-issue-list]`),buildIssues:document.querySelector(`[data-build-issues]`),objectList:document.querySelector(`[data-object-list]`),savedViews:document.querySelector(`[data-saved-views]`),properties:document.querySelector(`[data-properties]`),propertyActions:document.querySelector(`[data-property-actions]`),railToggle:document.querySelector(`[data-rail-toggle]`),resetView:document.querySelector(`[data-reset-view]`),cameraControls:document.querySelector(`[data-camera-controls]`),canvas:document.querySelector(`[data-canvas]`),workspace:document.querySelector(`[data-viewer-workspace]`),viewport:document.querySelector(`.viewport`),gallery:document.querySelector(`[data-gallery]`),galleryLink:document.querySelector(`[data-gallery-link]`),bundlePicker:document.querySelector(`[data-bundle-picker]`),modeSwitch:document.querySelector(`[data-mode-switch]`),codePane:document.querySelector(`[data-code-pane]`),codeTabs:document.querySelector(`[data-code-tabs]`),codeCase:document.querySelector(`[data-code-case]`),codeCaseStatus:document.querySelector(`[data-code-case-status]`),codeInputs:document.querySelector(`[data-code-inputs]`),inputCount:document.querySelector(`[data-input-count]`),compareCases:document.querySelector(`[data-compare-cases]`),buildInputs:document.querySelector(`[data-case-inputs="build"]`),reviewInputs:document.querySelector(`[data-case-inputs="review"]`),commText:document.querySelector(`[data-comm-text]`),codeState:document.querySelector(`[data-code-state]`),codeMeshToggle:document.querySelector(`[data-code-mesh-toggle]`),codeRun:document.querySelector(`[data-code-run]`),codeDownload:document.querySelector(`[data-code-download]`),codeReset:document.querySelector(`[data-code-reset]`),codeGutter:document.querySelector(`[data-code-gutter]`),codeText:document.querySelector(`[data-code-text]`),codeSelectionMark:document.querySelector(`[data-code-mark="selection"]`),codeErrorMark:document.querySelector(`[data-code-mark="error"]`),codeProblem:document.querySelector(`[data-code-problem]`),codeFoot:document.querySelector(`[data-code-foot]`),codeResize:document.querySelector(`[data-code-resize]`),codeCallMark:document.querySelector(`[data-code-mark="call"]`),codeRevealMark:document.querySelector(`[data-code-mark="reveal"]`),solveButton:document.querySelector(`[data-solve]`),reviewEmpty:document.querySelector(`[data-review-empty]`),reviewEmptyText:document.querySelector(`[data-review-empty-text]`),reviewEmptySolve:document.querySelector(`[data-review-empty-solve]`)},Yb=new URLSearchParams(window.location.search),Xb=Object.freeze({requestedBundle:Yb.get(`bundle`),embed:Yb.get(`embed`)===`1`,previewWebSocketUrl:Yb.get(`preview_ws`)}),Zb=null,Qb=`.`,$b=new Map,Y=null,ex=!1,tx=!1,nx=null;function X(e){return[`setModelColorBy`,`setColorChannel`,`setColoringField`,`setColoringComponent`,`setActiveLoadCase`,`setActiveResultState`,`setActiveGeometryState`].includes(e.type)&&(ex=!0),[`setActiveGeometryState`,`setActiveResultState`,`setActiveLoadCase`,`setVisualDeformationScale`,`setLayerVisibility`,`setBodyVisibility`,`setOverlayVisibility`,`applySectionBox`,`restoreVisibility`,`hideSelected`,`isolateSelection`,`resetLayerVisibility`,`restoreViewState`].includes(e.type)&&(bx=[],yx=!1),Y=Ub(Y,e),e.type===`setActiveLoadCase`&&Z.codeTab!==null&&(Z.codeTab=Nw().includes(e.loadCase)?e.loadCase:null,Z.codeTab!==null&&Rw()),e.type===`selectObject`&&(rx=g(Y,e.objectId)),e.type===`selectObjects`&&(rx=Y.selectedObjectIds[0]??null),Y}var rx=null,ix=``,ax={operatingOnly:!1},ox=!0,sx=[],cx=0,lx=4,ux=null,dx=!1,fx=null,px=null,mx=null,hx=null,gx=!1,_x=null,vx=!1,yx=!1,bx=[],xx=globalThis.__tubaViewerBootId??`boot:${Date.now()}:${Math.random().toString(16).slice(2)}`;globalThis.__tubaViewerBootId=xx;var Z={available:!1,ranCode:``,running:!1,error:null,selectionLine:null,callLine:null,revealedObjectId:null,revealLine:null,linesMoved:!1,tabLeavesEditor:!1,project:null,hasReview:!1,reviewStale:!1,solving:!1,solveStartedAt:null,preparing:!1,codeTab:null,commRequest:0},Q={available:!1,baseUrl:`.`,scriptUri:null,loadCases:[],text:new Map},Sx=new Map,Cx=null,wx=``;function Tx(){return!Z.available&&Q.available&&J.codeText.value!==Z.ranCode}async function Ex(){let{catalog:t,error:r}=await jx();if($b=new Map(i(t).map(e=>[n(e.id),e.title])),document.body.dataset.embed=String(Xb.embed),J.appShell.dataset.embed=String(Xb.embed),Ax(J.viewerIdentity,`Viewer`,`sha256:276b739a223c75ec98e0d1af3d4d1a9d4abdb07e0a0edff3170a29990029d91d`),r&&!Xb.requestedBundle){tw({message:r},`The gallery could not be listed.`);return}let o=a(t);Qb=Wn(Xb.requestedBundle,o),await Sw(t)&&!Xb.requestedBundle&&(Qb=`build`),document.body.dataset.view=`review`,J.galleryLink&&(J.galleryLink.hidden=o.length<=1||Xb.embed);try{ew(`Loading ${Qb}`),await Px(Qb,{preserve:!1}),ew(`Ready`),$(),Mx(t),await Cw(t),nx=e(J.exchangeDialog,{project:Z.project,catalogEntry:i(t).find(e=>n(e.id)===n(Qb)),reload:async()=>{await Px(Qb,{preserve:!0}),$()}}),J.exchangeOpen.addEventListener(`click`,()=>{J.exchangeDialog.showModal(),nx?.()});let r=Z.available?await Dx(Z.ranCode):i(t).find(e=>n(e.id)===n(Qb))?.build_identity??(Q.available?await Dx(Q.text.get(Q.scriptUri)??``):``);Ax(J.buildIdentity,`Source`,r),Ax(J.viewerIdentity,`Viewer`,`sha256:276b739a223c75ec98e0d1af3d4d1a9d4abdb07e0a0edff3170a29990029d91d`);let a=Xb.previewWebSocketUrl??(Z.available?ww():null);a&&nw(a)}catch(e){tw(e,`This review could not be opened.`)}}async function Dx(e){let t=await crypto.subtle.digest(`SHA-256`,new TextEncoder().encode(e));return`sha256:${[...new Uint8Array(t)].map(e=>e.toString(16).padStart(2,`0`)).join(``)}`}var Ox=[[/failed to load .*?(scene\.json|review\.json|metadata)/i,`A review file is missing from this bundle.`],[/\b(404|not found)\b/i,`That file is not in this bundle. It may be an incomplete export.`],[/\b(401|403|forbidden|unauthorized)\b/i,`The studio refused this request. Reload the page and sign in again if prompted.`],[/\b(5\d\d)\b/,`The studio server failed while handling the request. Try again; if it persists the server log has the detail.`],[/\b(abort|timeout|timed out|networkerror|failed to fetch|load failed)\b/i,`The studio could not be reached. Check that it is still running, then retry.`],[/websocket|live preview.*(closed|disconnect|invalid)/i,`The live connection to the studio dropped. Reload to reconnect.`],[/webgl2?/i,`This browser could not start WebGL2. The review report carries the processed result tables.`]];function kx(e,t=``){let n=String(e?.message??e??``).trim(),r=n.split(`
`).find(e=>e.trim())??``,i=/\n\s+File "|Traceback \(most recent call last\)/.test(n),a=i?r:n;for(let[e,r]of Ox)if(e.test(a))return{message:t?`${t} ${r}`:r,detail:n||null};return n?{message:t?`${t} ${a}`:a,detail:i?n:null}:{message:t?`${t} The reason was not reported.`:`Something failed, and the reason was not reported.`,detail:null}}function Ax(e,t,n){e.textContent=n?`${t} ${n.replace(/^sha256:/,``).slice(0,12)}`:``,e.title=n?`${t} ${n}`:``,n?e.setAttribute(`aria-label`,`${t} ${n}`):e.removeAttribute(`aria-label`)}async function jx(){let e;try{e=await fetch(`./bundles.json`)}catch(e){return{catalog:[],error:`The gallery catalog could not be loaded (${e.message})`}}if(!e.ok)return{catalog:[],error:`The gallery catalog is unavailable (HTTP ${e.status}).`};try{let t=await e.json();return Array.isArray(t)?{catalog:t,error:null}:{catalog:[],error:`The gallery catalog is not a list of reviews.`}}catch(e){return{catalog:[],error:`The gallery catalog is not readable JSON (${e.message}).`}}}function Mx(e){if(Xb.embed||Z.project||!J.bundlePicker)return;let t=i(e);if(t.length<=1){J.bundlePicker.hidden=!0;return}let r=n(Qb),a=t.map(e=>{let t=document.createElement(`option`);return t.value=e.id,t.textContent=e.title,t.selected=n(e.id)===r,t});if(r&&!a.some(e=>e.selected)){let e=document.createElement(`option`);e.value=Qb,e.textContent=r,e.selected=!0,a.unshift(e)}J.bundlePicker.replaceChildren(...a),J.bundlePicker.hidden=!1,lS(),J.bundlePicker.addEventListener(`change`,()=>Nx(J.bundlePicker.value,e))}async function Nx(e,t){Qb=e;let a=new URL(window.location.href);a.searchParams.set(`bundle`,e),window.history.replaceState({},``,a),ew(`Loading ${e}`);try{await Px(e,{preserve:!1});let a=i(t).find(t=>n(t.id)===n(e));r(J.exchangeDialog,a);let o=a?.build_identity??(Q.available?await Dx(Q.text.get(Q.scriptUri)??``):``);Ax(J.buildIdentity,`Source`,o),ew(`Ready`),$()}catch(e){tw(e,`That review could not be opened.`)}}async function Px(e,t={}){Yw(),Zb=await Kn(e),Z.project?kw():await Ow(e);let n=Pr(Yn(Zb)),r=Je({review:n.review,embed:Xb.embed}),i={...n,...r},a=t.preserve&&Y?Wb(Y,i,{reviewDefaultColor:t.reviewDefaultColor}):i;Y=Xb.embed?{...a,embed:!0,stage:`embed`}:a,bx=[],yx=!1}function $(){let e=Fx();jw(),lS(),zx(),Lx(),uS(),HS(),$x(),iC(),FC(),LC(),RC(),rT(),Fw(),XC(),Ix(e)}function Fx(){let e=document.activeElement,t=e?.dataset?.focusKey;return t?{key:t,start:typeof e.selectionStart==`number`?e.selectionStart:null,end:typeof e.selectionEnd==`number`?e.selectionEnd:null}:null}function Ix(e){if(!e||document.activeElement&&document.activeElement!==document.body)return;let t=globalThis.CSS?.escape??(e=>e),n=document.querySelector(`[data-focus-key="${t(e.key)}"]`);if(n&&(n.focus({preventScroll:!0}),e.start!==null&&typeof n.setSelectionRange==`function`))try{n.setSelectionRange(e.start,e.end)}catch{}}function Lx(){let e=Tw();J.taskRail.hidden=!e.railVisible,J.displayPalette.hidden=Dw()||Y.embed,J.displayPalette.hidden&&(J.displayPalette.open=!1),J.reviewDrawer.hidden=Dw()||Y.embed,J.railToggle.hidden=!e.railToggleVisible,J.railToggle.setAttribute(`aria-expanded`,String(ox)),J.railToggle.textContent=ox?`‹`:`›`,J.railToggle.title=ox?`Hide controls`:`Show controls`,J.railToggle.setAttribute(`aria-label`,J.railToggle.title),document.body.dataset.railOpen=String(ox),J.appHeader.hidden=!e.headerVisible}function Rx(){J.savedViews.replaceChildren();let e=document.createElement(`button`);e.type=`button`,e.textContent=`Save Current View`,e.dataset.focusKey=`saved-view:save`,e.addEventListener(`click`,()=>{let e=`View ${sx.length+1}`;sx.push(_i(Y,e)),$()}),J.savedViews.append(e);for(let[e,t]of sx.entries()){let n=document.createElement(`button`);n.type=`button`,n.textContent=t.name,n.dataset.focusKey=`saved-view:${e}`,n.addEventListener(`click`,()=>{X({type:`restoreViewState`,view:t}),rx=Y.selectedObjectIds[0]??null,$()}),J.savedViews.append(n)}}function zx(){J.statusStrip.hidden=Y.embed,Ux(),Bx(),Vx(),NS(),PS(),J.analysisDetails.hidden=J.discretisationCheck.hidden&&J.balanceCheck.hidden,Hx(),J.stripUnits.replaceChildren(...Y.embed?[]:[RS()])}function Bx(){let e=Ky(Y.review);J.solverFact.hidden=!e,J.solverFact.textContent=e,J.solverFact.title=e?`Solver, runtime version and load cases behind this review`:``}function Vx(){let e=je(Y);J.applicabilityFact.hidden=!e,e&&(J.applicabilityFact.textContent=e,J.applicabilityFact.title=`The field colouring this scene is finite-element output, not a code stress. It is for reviewing load paths and relative magnitudes, not for code compliance.`,J.applicabilityFact.setAttribute(`role`,`note`))}function Hx(){let e=Y.selectedObjectIds??[];if(J.selectionFact.hidden=e.length===0,e.length===0)return;let t=rx??e[0],n=Y.objects.find(e=>e.id===t)?.name||t;J.selectionFact.textContent=e.length>1?`${n} · ${e.length} selected`:n,J.selectionFact.title=`${e.length} object${e.length===1?``:`s`} selected`}function Ux(){J.statusChip.replaceChildren();let e=Z.project&&!Y.embed;Hw(!!(e&&(Z.solving||Z.preparing)));let t=e?Gx():Wx();if(!t){J.statusChip.hidden=!0;return}Kx(t)}function Wx(){if(!Z.available&&Q.preview&&Dw())return{status:`not_solved`,alerts:[`Browser geometry preview`],ariaLabel:`Geometry preview, not evaluated by Code_Aster`,onClick:()=>void Gw(`review`)};if(Y.embed||!Y.review)return null;let e=qy(Y.review),t=Tx(),n=t?`stale`:String(e.analysisStatus),r=[t?`Edited model · Code_Aster required`:null,e.warningCount>0?`${e.warningCount} warning${e.warningCount===1?``:`s`}`:null].filter(Boolean);return{status:n,alerts:r,clock:null,statusTarget:r.length>0?`issues`:`colour`,ariaLabel:`Analysis ${n}${r.length>0?`, ${r.join(`, `)}`:``} - show the review rail`,onClick:()=>{ox=!0,Gw(`review`).then(()=>{$();let e=r.length>0?J.issueList:J.colorBy;r.length>0?J.reviewDrawer.open=!0:J.colorBy.closest(`details`).open=!0,e?.scrollIntoView?.({block:`start`})})}}}function Gx(){if(!Z.project.solves&&!Z.reviewStale)return null;let[e,t]=Z.preparing?[`preparing`,`Importing the review`]:Z.solving?[`solving`,`Code_Aster is running`]:Z.hasReview?Z.reviewStale?[`stale`,`Model changed since the last solve`]:[`solved`,null]:[`not_solved`,null],n=Z.solving||Z.preparing;return{status:e,alerts:t?[t]:[],clock:n?Vw():null,statusTarget:null,ariaLabel:`Review ${e.replaceAll(`_`,` `)}${t?`, ${t}`:``} - show the review`,onClick:()=>void Gw(`review`)}}function Kx(e){J.statusChip.hidden=!1;let t=document.createElement(`span`);t.className=`status-badge`,t.dataset.status=e.status,t.textContent=e.status.replaceAll(`_`,` `),J.statusChip.append(t);for(let t of e.alerts){let e=document.createElement(`span`);e.className=`status-chip-alert`,e.textContent=t,J.statusChip.append(e)}if(e.clock){let t=document.createElement(`span`);t.className=`status-chip-clock`,t.textContent=e.clock,J.statusChip.append(t)}e.statusTarget?J.statusChip.dataset.statusTarget=e.statusTarget:delete J.statusChip.dataset.statusTarget,J.statusChip.setAttribute(`aria-label`,e.ariaLabel),J.statusChip.onclick=e.onClick}var qx=`model:`,Jx=`results:legacy`;function Yx(){if(!J.colorBy||!J.colorLegend)return;J.colorBy.replaceChildren(),J.colorLegend.replaceChildren();let e=Be(Y),t=Hg.map(e=>({id:`${qx}${e.id}`,label:e.label,group:`Model`})),n=P(Y).map(e=>({id:e.id,label:e.label,group:`Results`}));n.length===0&&e===`results`&&n.push({id:Jx,label:Et(Y)?.field??`Results`,group:`Results`});let r=Ce(Y)?.id,i=e===`results`?n.some(e=>e.id===r)?r:n[0]?.id:`model:${Y.modelColorBy??`default`}`;if(J.colorBy.append(Xx([...t,...n],i)),e===`results`){let e=Et(Y),t=Ce(Y);J.fieldDetails.hidden=!t&&!e,J.fieldDescription.textContent=t?`Solver field: ${t.label||t.id}. Support: ${t.support||`unspecified`}.`:e?.field??``,dS(e),fS(),pS(e),e||J.colorLegend.append(iw(`No result field to colour by.`));return}J.fieldDetails.hidden=!0;let a=Y.modelColorBy??`default`;a!=="default"&&J.colorLegend.append(Zx(a))}function Xx(e,t){let n=document.createElement(`div`);n.className=`field-select`;let r=document.createElement(`select`);r.setAttribute(`aria-label`,`Colour the scene by`),sw(r,`Colour by`);for(let n of[`Model`,`Results`]){let i=e.filter(e=>e.group===n);if(i.length===0)continue;let a=document.createElement(`optgroup`);a.label=n;for(let e of i){let n=document.createElement(`option`);n.value=e.id,n.textContent=e.label,n.selected=e.id===t,a.append(n)}r.append(a)}return r.addEventListener(`change`,()=>{let e=r.value;e.startsWith(qx)?X({type:`setModelColorBy`,colorBy:e.slice(6)}):X(e===Jx?{type:`setColorChannel`,colorChannel:`results`}:{type:`setColoringField`,fieldId:e}),$()}),n.append(r),n}function Zx(e){let t=Gg(Y,e);if(t.items.length===0)return iw(`No model elements found.`);let n=document.createElement(`div`);n.className=`model-legend-list`,n.setAttribute(`role`,`list`),n.setAttribute(`aria-label`,`Colouring legend by ${e}`);for(let r of t.items){let t=document.createElement(`button`);t.type=`button`,t.className=`model-legend-chip`,t.dataset.focusKey=`legend:${r.label}`,t.setAttribute(`role`,`listitem`),t.title=`Click to select ${r.count} elements with ${e} "${r.label}"`;let i=document.createElement(`span`);i.className=`model-legend-swatch`,i.style.backgroundColor=r.color;let a=document.createElement(`span`);a.className=`model-legend-label`,a.textContent=r.label;let o=document.createElement(`span`);o.className=`model-legend-tally`,o.textContent=String(r.count),t.append(i,a,o),t.addEventListener(`click`,()=>{X({type:`selectObjects`,objectIds:r.objectIds}),rx=Y.selectedObjectIds[0]??null,$()}),n.append(t)}return n}function Qx(){J.reactionTable.replaceChildren();let e=Y.activeResultStateId,t=(Y.review?.tables?.reactions?.rows??[]).filter(t=>t.result_state_id===e&&(!Y.activeLoadCase||t.load_case===Y.activeLoadCase));if(J.reactionTable.parentElement.hidden=t.length===0,!t.length)return;let n=document.createElement(`table`),r=n.createTHead().insertRow(),i=[[`node_id`,`Node`],[`support_ids`,`Supports`],[`fx`,`Fx`,`N`],[`fy`,`Fy`,`N`],[`fz`,`Fz`,`N`],[`mx`,`Mx`,`N*m`],[`my`,`My`,`N*m`],[`mz`,`Mz`,`N*m`]];for(let[,e]of i){let t=document.createElement(`th`);t.scope=`col`,t.textContent=e,r.append(t)}let a=n.createTBody();for(let e of t){let t=a.insertRow();for(let[n,,r]of i){let i=t.insertCell();if(n===`support_ids`)for(let t of e.support_ids??[]){let n=document.createElement(`button`);n.type=`button`,n.textContent=t;let r=hn(Y,t);n.disabled=!r,n.dataset.focusKey=`reaction:${e.node_id}:${t}`,n.setAttribute(`aria-pressed`,String(Y.selectedObjectIds.includes(r))),n.addEventListener(`click`,e=>{X({type:`selectObject`,objectId:r,additive:e.shiftKey}),$()}),i.append(n)}else i.textContent=r?N(e[n],r,O(Y))||`unavailable`:e[n]}}J.reactionTable.append(n)}function $x(){J.resultControls.replaceChildren(),J.resultShape.replaceChildren(),J.hotspotList.replaceChildren();for(let[e,t]of[[`table`,J.contactTable],[`display`,J.contactDisplay]]){t.replaceChildren();let n=Tn(Y,X,$,e);t.hidden=!n,n&&t.append(n)}Qx(),mS(),J.reviewTally.textContent=rC();let e=dt(Y),t=ft(Y),n=gt(Y),r=P(Y);if(e.length===0&&t.length===0&&n.length===0&&r.length===0){J.resultControls.append(iw(`No Code_Aster result overlays.`));return}let i=Be(Y)===`results`&&r.length>0&&I(Y);if(e.length>0&&J.resultControls.append(ow(`Case`,cw(Y.activeLoadCase??e[0].id,e,e=>{X({type:`setActiveLoadCase`,loadCase:e}),$()}))),i){let e={magnitude:`Magnitude`,N:`N (Axial Force)`,VY:`VY (Shear Force Y)`,VZ:`VZ (Shear Force Z)`,MT:`MT (Torsion)`,MFY:`MFY (Bending Moment Y)`,MFZ:`MFZ (Bending Moment Z)`},t=(Ce(Y)?.components??[`magnitude`]).map(t=>({id:t,label:e[t]??t}));J.resultControls.append(ow(`Component`,cw(we(Y),t,e=>{X({type:`setColoringComponent`,component:e}),$()})))}if(yt(Y)&&pt(Y).length>1){let e=Sn(Y,X,$);e&&(J.resultControls.append(aw(`Load path`,`${pt(Y).length} stages`)),J.resultControls.append(e.nav),J.resultControls.append(e.steps))}else (t.length>1||r.length===0&&t.length>0)&&J.resultControls.append(ow(`Step`,cw(Y.activeResultStateId??t[0].id,t,e=>{X({type:`setActiveResultState`,resultStateId:e}),$()})));J.resultShape.append(aw(`Deformation`,`\u00d7${yw(Vt(Y))}`)),!yt(Y)&&n.length>0&&J.resultShape.append(ow(`Deformed state`,cw(Y.activeGeometryStateId??n[0].id,n,e=>{hw(),X({type:`setActiveGeometryState`,geometryStateId:e}),$()}))),J.resultShape.append(ow(`Deform`,zS())),J.resultShape.append(nS());let a=kt(Y);if(J.hotspotList.append(aw(`Hotspots`,eS(a))),a.length===0){let e=document.createElement(`div`);e.className=`meta`,e.textContent=`No hotspots above threshold.`,J.hotspotList.append(e);return}let o=Et(Y),s=Ft(Y),c=Ne(Y);for(let[e,t]of a.entries()){let n=document.createElement(`button`);n.type=`button`,n.className=`hotspot-row`,t.objectId===Y.activeFindingObjectId&&(n.classList.add(`hotspot-active`),n.setAttribute(`aria-current`,`true`)),n.dataset.hotspotIndex=String(e),n.dataset.focusKey=`hotspot:${t.elementId??``}:${t.rowIndex??``}:${t.subpointIndex??``}`;let r=t.elementId?` ${t.elementId} row ${t.rowIndex??`?`} subpoint ${t.subpointIndex??`?`}`:``,i=N(t.value,t.unit,O(Y)),l=document.createElement(`span`);l.className=`hotspot-dot`;let u=zt(t.value,o);u!==null&&(l.style.background=uw(u));let d=document.createElement(`span`);d.className=`hotspot-name`,d.textContent=`${t.objectName}${r} `;let f=document.createElement(`span`);if(f.className=`hotspot-value`,f.textContent=t.utilization===null?i:`${i} `,n.append(l,d,f),t.utilization!==null){let e=document.createElement(`span`);e.className=`hotspot-util`,e.textContent=`u=${yw(t.utilization)}`,n.append(e)}if(c?.winners?.[t.objectId]){let e=c.resultStates.find(e=>e.id===c.winners[t.objectId]),r=document.createElement(`span`);r.className=`hotspot-step`,r.textContent=e?.label??c.winners[t.objectId],r.title=`The result step that produced this element's envelope value`,n.append(r)}if(t.objectId===Y.activeFindingObjectId&&s>=0){let e=document.createElement(`span`);e.className=`hotspot-position`,e.textContent=`${s+1}/${a.length}`,n.append(e)}let p=bS(t),m=p?$v(Y,p.subjectId):null;if(p){let e=document.createElement(`span`);e.className=`hotspot-disposition disposition-${m?.status??`none`}`,e.textContent=m?Hv(m.status)?.label??m.status:`unreviewed`,n.append(e)}n.addEventListener(`click`,()=>{rx=t.objectId,X({type:`focusFinding`,objectId:t.objectId}),$()}),J.hotspotList.append(n)}}function eS(e){let t=Y.resultThreshold;if(!(Number(t)>0))return`${e.length}`;let n=Et(Y)?.unit??``;return`${e.length} above ${N(t,n,O(Y))}`}var tS=!1;function nS(){let e=document.createElement(`details`);e.className=`strip-drawer`,e.dataset.resultFilters=``,e.open=tS,e.addEventListener(`toggle`,()=>{tS=e.open});let t=document.createElement(`summary`);t.append(`Filters & vectors`);let n=document.createElement(`span`);return n.className=`drawer-state`,n.textContent=rS(),t.append(n),e.append(...[t,oS(),iS(),_w(`Utilization threshold`,Y.utilizationThreshold??``,`0.05`,e=>{X({type:`setUtilizationThreshold`,threshold:e}),$()}),cS(),vw(`Displacement vector scale ${yw(Y.resultVectorScales?.displacement??1)}x`,Y.resultVectorScales?.displacement??1,0,20,.5,e=>{X({type:`setDisplacementVectorScale`,scale:e}),$()},`Displacement vector scale`),vw(`Moment vector scale ${yw(Y.resultVectorScales?.moment??1)}x`,Y.resultVectorScales?.moment??1,0,5,.25,e=>{X({type:`setMomentVectorScale`,scale:e}),$()},`Moment vector scale`),vw(`Reaction vector scale ${yw(Y.resultVectorScales?.reaction??1)}x`,Y.resultVectorScales?.reaction??1,0,5,.25,e=>{X({type:`setReactionVectorScale`,scale:e}),$()},`Reaction vector scale`)].filter(Boolean)),e}function rS(){return[Y.resultVectorScales?.displacement??1,Y.resultVectorScales?.moment??1,Y.resultVectorScales?.reaction??1].map(e=>yw(e)).join(` / `)}function iS(){let e=Et(Y)?.unit??``,t=O(Y),n=te(e)?` (${j(e,t)})`:e?` (${e})`:``,r=Y.resultThreshold,i=Number.isFinite(Number(r))&&r!==null?M(r,e,t):``,a=M(aS,e===`Pa`?e:``,t)||1;return _w(`Stress threshold${n}`,i,String(a),n=>{let r=String(n).trim();X({type:`setResultThreshold`,threshold:r===``?0:re(r,e,t)}),$()},`Stress threshold`)}var aS=1e6;function oS(){let e=Et(Y);if(!e)return null;let t=document.createElement(`div`);t.className=`scale-controls`;let n=document.createElement(`label`);n.className=`scale-band-label`,n.textContent=`Bands`;let r=document.createElement(`select`);r.dataset.focusKey=`legend-bands`,r.setAttribute(`aria-label`,`Colour band count`);for(let e of Ze){let t=document.createElement(`option`);t.value=String(e),t.textContent=e===0?`continuous`:String(e),t.selected=Number(Y.legendBands??0)===e,r.append(t)}r.addEventListener(`change`,()=>{X({type:`setLegendBands`,bands:Number(r.value)}),$()}),n.append(r),t.append(n);let i=O(Y),a=e.unit??``,o=at(e),s=Number(e.range?.min??0),c=Number(e.range?.max??0);for(let[e,n]of[[`min`,s],[`max`,c]]){let r=document.createElement(`label`);r.className=`scale-bound-label`,r.textContent=e===`min`?`From`:`To`;let o=document.createElement(`input`);o.type=`number`,o.step=`any`,o.value=String(sS(te(a)?M(n,a,i):n)),o.dataset.focusKey=`legend-range-${e}`,o.setAttribute(`aria-label`,`Legend ${e}`),o.addEventListener(`change`,()=>{let t={min:s,max:c,[e]:Number(o.value)};X({type:`setLegendRange`,range:{min:te(a)?re(t.min,a,i):t.min,max:te(a)?re(t.max,a,i):t.max}}),$()}),r.append(o),t.append(r)}let l=document.createElement(`div`);l.className=`scale-actions`;let u=document.createElement(`button`);if(u.type=`button`,u.className=`bar-button`,u.dataset.focusKey=`legend-nice`,u.textContent=`Round bounds`,u.title=`Snap both ends to round numbers so the band increments are round`,u.addEventListener(`click`,()=>{let e=$e(s,c,Number(Y.legendBands??0));X({type:`setLegendRange`,range:{min:te(a)?re(e.min,a,i):e.min,max:te(a)?re(e.max,a,i):e.max}}),$()}),l.append(u),o||Number(Y.legendBands??0)>0){let e=document.createElement(`button`);e.type=`button`,e.className=`bar-button`,e.dataset.focusKey=`legend-reset`,e.textContent=`Reset`,e.title=`Return the ramp to the field's own range, continuously scaled`,e.addEventListener(`click`,()=>{X({type:`resetLegendScale`}),$()}),l.append(e)}return t.append(l),t}function sS(e){return Number.isFinite(e)?Number(e.toPrecision(6)):0}function cS(){let e=Pt(Y);if(e.length===0)return null;let t=document.createElement(`button`);return t.type=`button`,t.className=`bar-button select-findings`,t.dataset.focusKey=`select-findings`,t.textContent=`Select ${e.length} finding${e.length===1?``:`s`}`,t.title=`Select every finding the current thresholds leave, so the review tables can be scoped to them`,t.addEventListener(`click`,()=>{rx=e[0].objectId,X({type:`selectObjects`,objectIds:e.map(e=>e.objectId)}),X({type:`setActiveFinding`,objectId:e[0].objectId}),$()}),t}function lS(){J.sceneTitle.textContent=!Z.project&&$b.get(n(Qb))||(Y.review?.project_name??String(Y.sceneId??``).replace(/^scene:/,``)),J.sceneTitle.classList.toggle(`visually-hidden`,!J.bundlePicker.hidden),J.sceneMeta.textContent=Y.review?[Y.review.model_standard,`Revision ${Y.review.model_revision}`].filter(Boolean).join(` · `):`${Y.objects.length} objects | ${Y.issues.length} issues`,J.reportLink.hidden=!Y.review,Y.review?(J.reportLink.href=`${Qb}/index.html`,J.reportLink.title=`Engineering review tables. Printed in stored SI units (m, Pa, N), not the display units used here.`,J.reportLink.setAttribute(`aria-label`,`Report - engineering review tables, printed in stored SI units rather than the display units used here`)):J.reportLink.removeAttribute(`href`)}function uS(){J.displayStrip.hidden=Y.embed,Yx(),xS(),CS(),DS(),OS(),pC(),tC(ur(Y.layers)),ZS(),Rx(),AC()}function dS(e){let t=My(Y,e);J.averagingNote.hidden=!t,J.averagingNote.textContent=t?`Value basis: ${t}.`:``}function fS(){J.referenceNote.replaceChildren();let e=jt(Y);if(J.referenceNote.hidden=!e,!e)return;let t=O(Y),n=document.createElement(`span`);n.className=`reference-lead`,n.textContent=`Reference stress:`;let r=e.percentiles.map(n=>`${N(n.value,e.unit,t)} exceeded in ${dw(n.fraction)} of wall points`),i=document.createElement(`span`);i.className=`reference-values`,i.textContent=`${r.join(` · `)}. Peak ${N(e.max,e.unit,t)} at a single point.`;let a=document.createElement(`span`);a.className=`reference-basis`,a.textContent=e.truncated?`Based on ${e.count} of ${e.declaredCount} sub-points Code_Aster wrote, so the population is incomplete.`:`Unlike the peak, this is insensitive to mesh density and notch radius, so it can be compared across runs.`,J.referenceNote.append(n,i,a)}function pS(e){J.envelopeNote.replaceChildren();let t=e?.envelope;if(J.envelopeNote.hidden=!t,!t)return;let n=[];t.sources?.length&&n.push(`Maximum over the result steps of ${t.sources.map(e=>e.label).join(`, `)}`);let r=document.createElement(`span`);if(!t.enveloped){r.textContent=`Only one result step carried this quantity, so no maximum was taken across steps.`,J.envelopeNote.append(r);return}t.resultStateIds?.length&&n.push(`${t.resultStateIds.length} result step${t.resultStateIds.length===1?``:`s`} combined`),r.textContent=`${n.join(` · `)}. Derived from the solved results, not a separate solve; the hotspot list names the step that governs each element.`,J.envelopeNote.append(r)}function mS(){let e=J.runDiagram;if(!e)return;let t=hS(),n=t?vy(Y,t):[];if(e.hidden=!t||n.length===0,e.hidden)return;let r=Y.runDiagramComponent,i=n.find(e=>e.id===r)??n[0],a=_y(Y,t,i.id);J.runDiagramSummary.textContent=a?`${i.id} along ${t.label}`:`Run diagram`;let o=J.runDiagramBody;if(o.replaceChildren(),!a){o.append(iw(`This run publishes no end forces for the selected component.`));return}if(n.length>1){let e=document.createElement(`div`);e.className=`diagram-components`,e.setAttribute(`role`,`group`),e.setAttribute(`aria-label`,`Diagram component`);for(let t of n){let n=document.createElement(`button`);n.type=`button`,n.className=`bar-button${t.id===i.id?` diagram-component-active`:``}`,n.dataset.focusKey=`diagram:${t.id}`,n.textContent=t.id,n.title=`${t.label} — ${t.unit}`,n.setAttribute(`aria-pressed`,String(t.id===i.id)),n.addEventListener(`click`,()=>{X({type:`setRunDiagramComponent`,component:t.id}),$()}),e.append(n)}o.append(e)}let s=document.createElement(`div`);s.className=`diagram-chart`,s.innerHTML=by(a,{width:720,height:220}),o.append(s);let c=document.createElement(`p`);c.className=`diagram-facts`;let l=O(Y),u=a.points.reduce((e,t)=>Math.abs(t.value)>Math.abs(e.value)?t:e);if(c.textContent=`${a.points.length} ordinates over ${N(a.extent.station.max,`m`,l)} of run. Peak ${N(Math.abs(u.value),a.unit,l)} at ${N(u.station,`m`,l)}, ${u.elementId} ${u.end}.`,a.missing>0){let e=document.createElement(`span`);e.className=`diagram-gap`,e.textContent=` ${a.missing} member${a.missing===1?``:`s`} carried no end forces and ${a.missing===1?`is`:`are`} left as a gap.`,c.append(e)}o.append(c)}function hS(){let e=Y.runDiagramRunId;if(e){let t=uy(Y).find(t=>t.id===e);if(t)return t}let t=Y.selectedObjectIds??[];for(let e of t){let t=dy(Y,e);if(t)return t}return null}function gS(){let e=_S();if(!e)return null;let t=document.createElement(`button`);return t.type=`button`,t.className=`bar-button`,t.dataset.focusKey=`run-diagram`,t.dataset.runDiagramRun=e.id,t.textContent=`Plot this run`,t.title=`Station diagram along ${e.label}`,t.addEventListener(`click`,()=>{X({type:`setRunDiagramRun`,runId:e.id}),vS()}),t}function _S(){for(let e of Y.selectedObjectIds??[]){let t=dy(Y,e);if(t)return t}return null}function vS(){!J.runDiagram||J.runDiagram.hidden||(J.runDiagram.open=!0,J.runDiagram.scrollIntoView({block:`nearest`}))}function yS(){let e=_S();e&&(Y.runDiagramRunId!==e.id&&X({type:`setRunDiagramRun`,runId:e.id}),$(),vS())}function bS(e){let t=Et(Y);if(!e||!t)return null;let n={fieldId:t.fieldId??null,component:t.component??null,resultStateId:Y.activeResultStateId??null,loadCase:Y.activeLoadCase??null,unit:t.unit??null},r=qv(e,n);return r?{subjectId:r,address:Xv(e,n)}:null}function xS(){J.bodyList.replaceChildren();let e=kr(Y);if(e.length===0){J.bodyList.append(iw(`This scene draws no result bodies.`));return}for(let t of e)J.bodyList.append(SS(t))}function SS(e){let t=document.createElement(`div`);t.className=`body-row`,t.dataset.body=e.id,t.dataset.bodyVisible=String(e.visible);let n=document.createElement(`div`);n.className=`body-head`;let r=document.createElement(`label`);r.className=`body-toggle`;let i=document.createElement(`input`);i.type=`checkbox`,i.checked=e.visible,i.indeterminate=e.partiallyVisible,i.setAttribute(`aria-label`,e.label),i.dataset.focusKey=`body:${e.id}`,i.addEventListener(`change`,()=>{X({type:`setBodyVisibility`,bodyId:e.id,visible:i.checked}),$()});let a=document.createElement(`span`);a.className=`body-name`,a.textContent=e.label,r.append(i,a);let o=document.createElement(`span`);if(o.className=`body-badge body-badge-${e.badge.tone}`,o.textContent=e.badge.text,n.append(r,o),e.supportsOpacity&&n.append(ES(e)),e.metrics.length>0){let r=document.createElement(`div`);r.className=`body-metrics`,r.id=`body-metrics-${e.id}`,r.hidden=!DC.has(e.id);for(let t of e.metrics){let e=document.createElement(`p`);e.className=`body-metric`,e.textContent=t,r.append(e)}let i=document.createElement(`button`);return i.type=`button`,i.className=`body-caret`,i.dataset.focusKey=`metrics:${e.id}`,i.setAttribute(`aria-expanded`,String(!r.hidden)),i.setAttribute(`aria-controls`,r.id),i.setAttribute(`aria-label`,`${e.label} details`),i.textContent=r.hidden?`▸`:`▾`,i.addEventListener(`click`,()=>{DC.has(e.id)?DC.delete(e.id):DC.add(e.id),$()}),n.append(i),t.append(n,r),t}return t.append(n),t}function CS(){let e=wr(Y);J.overlaysBlock.hidden=e.length===0,J.overlayList.replaceChildren();for(let t of e)J.overlayList.append(wS(t))}function wS(e){let t=document.createElement(`div`);t.className=`body-row`,t.dataset.overlay=e.id,t.dataset.bodyVisible=String(e.visible);let n=document.createElement(`div`);n.className=`body-head`;let r=document.createElement(`label`);r.className=`body-toggle`;let i=document.createElement(`input`);i.type=`checkbox`,i.checked=e.visible,i.indeterminate=e.partiallyVisible,i.setAttribute(`aria-label`,e.label),i.dataset.focusKey=`overlay:${e.id}`,i.addEventListener(`change`,()=>{X({type:`setOverlayVisibility`,overlayId:e.id,visible:i.checked}),$()});let a=document.createElement(`span`);if(a.className=`body-name`,a.textContent=e.label,a.title=e.description,r.append(i,a),n.append(r),e.count!==null){let t=document.createElement(`span`);t.className=`body-badge body-badge-neutral`,t.textContent=String(e.count),n.append(t)}return e.vectorType&&n.append(TS(e)),t.append(n),t}function TS(e){let t=document.createElement(`button`);return t.type=`button`,t.className=`body-scale`,t.dataset.overlayScale=e.id,t.dataset.focusKey=`scale:${e.id}`,t.textContent=`${yw(e.scale)}x`,t.setAttribute(`aria-label`,`${e.label} scale ${yw(e.scale)}x, cycles through ${Sr.map(e=>`${yw(e)}x`).join(`, `)}`),t.addEventListener(`click`,()=>{X({type:Jb[e.vectorType],scale:Er(e.scale)}),$()}),t}function ES(e){let t=document.createElement(`button`);t.type=`button`,t.className=`body-opacity`,t.dataset.bodyOpacity=e.id,t.dataset.focusKey=`opacity:${e.id}`;let n=Math.round(e.opacity*100);return t.textContent=`${n}%`,t.setAttribute(`aria-label`,`${e.label} opacity ${n}%, cycles through ${_r.map(e=>`${Math.round(e*100)}%`).join(`, `)}`),t.addEventListener(`click`,()=>{X({type:`cycleBodyOpacity`,bodyId:e.id}),$()}),t}function DS(){let e=Ce(Y)?.support===`subpoint`&&zr(Y);if(J.projectionNote.hidden=!e,!e){J.projectionNote.textContent=``;return}J.projectionNote.textContent=`Sub-points are measured; the surface between them is interpolated.`}function OS(){J.sectionProfile.replaceChildren();let e=zr(Y);if(J.sectionProfile.hidden=!e,!e)return;let t=document.createElement(`button`);if(t.type=`button`,t.className=`strip-heading strip-toggle`,t.dataset.focusKey=`section:wall`,t.setAttribute(`aria-expanded`,String(OC)),t.textContent=`${OC?`▾`:`▸`} Wall section`,t.addEventListener(`click`,()=>{OC=!OC,$()}),J.sectionProfile.append(t),!OC)return;let n=document.createElement(`div`);n.className=`section-profile-body`,n.append(MS(e));let r=document.createElement(`div`);r.className=`section-facts`,r.append(iw(`NSEC ${e.nsec} × NCOU ${e.ncou}`),iw(`${e.sectors} sectors × ${e.layers} layers = ${e.subpoints_per_node} per node`));let i=Zr(Y);if(i){let e=Br(Y)?.unit??i.unit??``,t=iw(`peak ${N(i.value,e,O(Y))}${i.location?` · ${i.location}`:``}`.trim());t.classList.add(`section-peak`),r.append(t)}let a=e.display_generatrice;Array.isArray(a)&&r.append(iw(`sector 0 on (${a.join(`, `)})`)),n.append(r),J.sectionProfile.append(n)}var kS=118,AS=1.1,jS=2.4;function MS(e){let t=document.createElementNS(`http://www.w3.org/2000/svg`,`svg`);t.setAttribute(`viewBox`,`0 0 ${kS} ${kS}`),t.setAttribute(`width`,String(kS)),t.setAttribute(`height`,String(kS)),t.setAttribute(`class`,`section-rosette`),t.setAttribute(`role`,`img`),t.setAttribute(`aria-label`,`Pipe section: ${e.sectors} circumferential sub-point stations across ${e.layers} wall layers`);let n=kS/2,r=n-6,i=r*.62;for(let e of[i,r]){let r=document.createElementNS(`http://www.w3.org/2000/svg`,`circle`);r.setAttribute(`cx`,String(n)),r.setAttribute(`cy`,String(n)),r.setAttribute(`r`,String(e)),r.setAttribute(`class`,`rosette-wall`),t.append(r)}let a=Br(Y),o=new Map;for(let e of Qr(Y)){let t=`${e.sectorIndex}:${e.layerIndex}`,n=o.get(t);(!n||e.value>n.value)&&o.set(t,e)}let s=Math.max(e.sectors-1,1),c=Math.max(e.layers-1,1);for(let l=0;l<e.layers;l+=1){let u=i+(r-i)*l/c;for(let r=0;r<e.sectors;r+=1){if(r===e.sectors-1)continue;let i=2*Math.PI*r/s,c=o.get(`${r}:${l}`),d=document.createElementNS(`http://www.w3.org/2000/svg`,`circle`);d.setAttribute(`cx`,(n+u*Math.sin(i)).toFixed(2)),d.setAttribute(`cy`,(n-u*Math.cos(i)).toFixed(2)),d.setAttribute(`r`,String(c?jS:AS)),d.setAttribute(`class`,c?`rosette-point`:`rosette-station`);let f=c?zt(c.value,a):null;f!==null&&d.setAttribute(`fill`,uw(f)),t.append(d)}}return t}function NS(){J.discretisationCheck.replaceChildren();let e=Vr(Y);if(J.discretisationCheck.hidden=!e,!e)return;let t=document.createElement(`span`);t.className=`check-label`,t.textContent=`Mesh`;let n=document.createElement(`span`);n.className=`check-value`,n.textContent=`${e.min_elements_per_bend}/bend · chord ${N(e.max_chord_deviation,e.unit,O(Y))}`;let r=document.createElement(`span`);r.className=`check-badge ${e.within_tolerance?`check-ok`:`check-warn`}`,r.textContent=`${e.within_tolerance?`OK`:`COARSE`} ≤ ${dw(e.tolerance_ratio)} R`,J.discretisationCheck.append(t,n,r);let i=e.worst_bend;if(i&&e.bend_count>1){let t=document.createElement(`span`);t.className=`check-worst`,t.textContent=`worst of ${e.bend_count}: ${i.source_element_id}`,J.discretisationCheck.append(t)}}function PS(){J.balanceCheck.replaceChildren();let e=FS();if(J.balanceCheck.hidden=!e,LS(),!e)return;let t=O(Y),n=document.createElement(`span`);n.className=`check-label`,n.textContent=`Balance`;let r=Ay(e.forceResidualRatio,e.tolerance),i=Ay(e.momentResidualRatio,e.tolerance),a=r&&i,o=document.createElement(`span`);o.className=`check-value`,o.textContent=[`Σ reaction ${N(e.reactionForce[2],`N`,t)} Z`,`residual ${N(e.forceResidual,`N`,t)}`].join(` · `);let s=document.createElement(`span`);s.className=`check-badge ${a?`check-ok`:`check-warn`}`,s.textContent=a?`closes over the terms present`:`residual ${dw(Math.max(e.forceResidualRatio??0,e.momentResidualRatio??0))} of summed terms`;let c=document.createElement(`span`);c.className=`check-worst`,c.textContent=e.complete?`summed: ${e.included.join(`, `)}`:`summed: ${e.included.join(`, `)} · not summed: ${e.omitted.join(`, `)}`,J.balanceCheck.append(n,o,s,c),J.balanceCheck.title=`Global equilibrium over the load terms this bundle carries. Code_Aster assembles self-weight, pressure and line loads internally, so those are named as excluded rather than silently dropped. This is a consistency check on the solve, not a code check.`}function FS(){return jy(Y,IS())}function IS(){let e=Y.activeResultStateId??null,t=xt(Y),n=n=>(Y.overlays??[]).find(r=>{let i=r.data??{};return!(i.result_type!==n||e&&i.result_state_id&&i.result_state_id!==e||t&&i.load_case&&i.load_case!==t)})?.data??null;return{reactionForce:n(`reaction_force`)?.values??null,reactionMoment:n(`reaction_moment`)?.values??null,loadCase:t,loadCaseDefinition:St(Y)}}function LS(){let e=Vr(Y),t=FS(),n=Ay(t?.forceResidualRatio,t?.tolerance??0),r=Ay(t?.momentResidualRatio,t?.tolerance??0);if(t&&!(n&&r)){J.analysisSummary.textContent=`Mesh & balance · warning`,J.analysisSummary.classList.add(`mesh-warning`);return}J.analysisSummary.textContent=e&&!e.within_tolerance?`Mesh detail · warning`:`Mesh detail`,J.analysisSummary.classList.toggle(`mesh-warning`,!!(e&&!e.within_tolerance))}function RS(){let e=T.find(e=>e.id===O(Y)),t=document.createElement(`button`);return t.type=`button`,t.className=`bar-button bar-units strip-units`,t.dataset.unitSystem=e.id,t.dataset.focusKey=`unit-system`,t.textContent=e.label,t.title=`${e.title} — click to switch`,t.setAttribute(`aria-label`,`Display units: ${e.title}`),t.addEventListener(`click`,()=>{X({type:`setUnitSystem`,unitSystem:A(Y)}),$()}),t}function zS(){let e=document.createElement(`div`);e.className=`deform-control`;let t=Vt(Y),n=document.createElement(`input`);n.type=`range`,n.min=`1`,n.max=`100`,n.step=`1`,n.value=String(t),n.setAttribute(`aria-label`,`Visual deformation scale (display only)`),n.dataset.focusKey=`deform-scale`,n.addEventListener(`input`,()=>{hw(),X({type:`setVisualDeformationScale`,scale:n.value}),r.textContent=`×${yw(Vt(Y))}`,ux?.renderDeformation(Y)||XC()}),n.addEventListener(`pointerdown`,()=>ux?.setDeformationInteraction(!0)),n.addEventListener(`change`,()=>{ux?.setDeformationInteraction(!1),$()});for(let e of[`pointerup`,`pointercancel`])n.addEventListener(e,()=>{ux?.setDeformationInteraction(!1)&&$()});let r=document.createElement(`span`);return r.className=`bar-readout`,r.dataset.deformScale=``,r.textContent=`×${yw(t)}`,e.append(n,r,BS()),e}function BS(){let e=document.createElement(`button`);e.type=`button`,e.className=`bar-button`,e.dataset.animateDeformation=``,e.dataset.focusKey=`deform-animate`;let t=pw!==null;return e.replaceChildren(lw(t?`pause`:`play`)),e.setAttribute(`aria-label`,t?`Pause deformation animation`:`Animate deformation`),e.setAttribute(`aria-pressed`,String(t)),e.disabled=!t&&!VS(),e.addEventListener(`click`,mw),e}function VS(){return gt(Y).some(e=>Number(e.visualScale)>1)}function HS(){J.viewportLegend.replaceChildren(),J.bodyLegend.replaceChildren();let e=Et(Y);if(J.viewportLegend.hidden=!e,e){let t=document.createElement(`div`);t.className=`legend-heading`;let n=document.createElement(`span`),r=e.component&&e.component!==`magnitude`?` ${e.component}`:``;n.textContent=`${e.field}${r}`;let i=document.createElement(`span`);i.className=`legend-context`;let a=O(Y);i.textContent=[j(e.unit,a),e.loadCase].filter(Boolean).join(` · `),t.append(n,i);let o=document.createElement(`div`);o.className=`legend-ramp`,o.dataset.legendRamp=``,o.dataset.legendBands=String(e.bands??0),o.style.background=qS(e),J.viewportLegend.append(t,o,...US(e),WS(e)),XS()}let t=kr(Y).filter(e=>e.visible),n=St(Y),r=new Set(Y.visibleObjectIds??[]),i=(Y.objects??[]).filter(e=>r.has(e.id)&&[`applied_load`,`reaction_vector`].includes(e.kind)),a=t.length>0||!!n||i.length>0||Pn(Y,r).length>0;if(J.bodyLegendToggle.hidden=Y.embed||!a,J.bodyLegendToggle.setAttribute(`aria-expanded`,String(kC)),J.bodyLegendToggle.title=kC?`Hide the viewport key`:`What the marks mean`,J.bodyLegendToggle.setAttribute(`aria-label`,J.bodyLegendToggle.title),J.bodyLegend.hidden=!a||!kC||Y.embed,J.bodyLegend.hidden)return;if(n){let e=O(Y),t=Number(n.nodal_force_count??0);GS(`${n.load_case} inputs — ${n.gravity?`gravity on`:`gravity off`} · pressure ${N(n.internal_pressure_pa,`Pa`,e)} · ${N(n.temperature_c,`°C`,e)} from ${N(n.ref_temperature_c,`°C`,e)} · ${t?`${t} imposed nodal force${t===1?``:`s`}`:`no imposed nodal forces`}`)}let o=new Map;for(let e of i){let t=e.metadata?.result_type,n=e.metadata?.vector_kind,r=e.kind===`applied_load`?`applied_${n}`:t,i={applied_force:`Applied force — authored input`,applied_moment:`Applied moment — authored input, right-hand rule`,applied_line_load:`Applied line load — authored input`,reaction_force:`Reaction force — Code_Aster result`,reaction_moment:`Reaction moment — Code_Aster result, right-hand rule`}[r];if(!i||o.has(r))continue;let a=Y.geometryAssets.find(t=>t.id===e.geometry_asset_id);o.set(r,{label:i,color:a?.generation_config?.color})}for(let{label:e,color:t}of o.values())GS(e,t);for(let e of Pn(Y,r))GS(jn[e],An[e]);for(let e of t)GS(`${e.label} — ${KS[e.id]??e.badge.text}`,null,`body-legend-${e.id}`)}function US(e){let t=O(Y),n=et(e),r=n.length<=9?n:[n[0],...n.filter((e,t)=>t>0&&t<n.length-1&&t%2==0),n[n.length-1]],i=document.createElement(`div`);i.className=`legend-ticks`,i.dataset.legendTicks=``;for(let n of r){let r=document.createElement(`span`);r.textContent=ie(n,e.unit,t),i.append(r)}return[i]}function WS(e){let t=O(Y),n=at(e),r=Number(e.bands)>0;if(!n&&!r)return[];let i=document.createElement(`div`);i.className=`legend-scale`,i.dataset.legendScale=``;let a=Number(e.range?.min??0),o=Number(e.range?.max??0),s=[`${ie(a,e.unit,t)} – ${ie(o,e.unit,t)}`];return r&&s.push(`${e.bands} bands`),i.textContent=s.join(` · `),n&&i.append(` (set by you)`),[i]}function GS(e,t=null,n=``){let r=document.createElement(`div`);if(r.className=`body-legend-row`,t||n){let e=document.createElement(`span`);e.className=`body-legend-swatch ${n}`.trim(),t&&(e.style.background=t),r.append(e)}let i=document.createElement(`span`);i.textContent=e,r.append(i),J.bodyLegend.append(r)}var KS=Object.freeze({geometry:`surface, interpolated`,analysis_mesh:`cell values`,subpoints:`measured`,deformed:`display scale only`});function qS(e){if(Number(e?.bands??0)>0)return JS(e);let t=Number(e.range?.min??0),n=Number(e.range?.max??1),r=[];for(let i=0;i<=12;i+=1){let a=i/12,o=zt(t+(n-t)*a,e);o!==null&&r.push(`${uw(o)} ${(a*100).toFixed(0)}%`)}return r.length>1?`linear-gradient(90deg, ${r.join(`, `)})`:`none`}function JS(e){let t=Number(e.bands),n=[];for(let r=0;r<t;r+=1){let i=zt(YS(e,r),e);if(i===null)continue;let a=(r/t*100).toFixed(2),o=((r+1)/t*100).toFixed(2);n.push(`${uw(i)} ${a}%`,`${uw(i)} ${o}%`)}return n.length>1?`linear-gradient(90deg, ${n.join(`, `)})`:`none`}function YS(e,t){let n=et(e),r=n[Math.min(t,n.length-2)]??0;return(r+(n[Math.min(t+1,n.length-1)]??r+1))/2}function XS(){let e=je(Y);if(!e)return;let t=document.createElement(`div`);t.className=`compliance-notice`,t.dataset.complianceNotice=``,t.textContent=`⚠ ${e}`,J.viewportLegend.append(t)}function ZS(){J.sectionBoxControls.replaceChildren();let e=document.createElement(`section`);e.className=`section-box-controls`;let t=document.createElement(`h3`);t.textContent=`Section`;let n=document.createElement(`input`);n.type=`checkbox`,n.checked=!!Y.sectionBox,n.id=`section-enabled`;let r=document.createElement(`label`);r.htmlFor=n.id,r.append(n,` Enable section`);let i=Y.sectionBox??gi(Y.bounds),a=[],o=document.createElement(`div`);o.className=`section-box-grid`;for(let[e,t]of[[`X`,0],[`Y`,1],[`Z`,2]])for(let r of[`min`,`max`]){let s=document.createElement(`label`);s.textContent=`${e} ${r}`;let c=document.createElement(`input`);c.type=`number`,c.step=`any`,c.value=String(i[r][t]),c.disabled=!n.checked,c.setAttribute(`aria-label`,`Section ${e} ${r}`),a.push({input:c,index:t,side:r}),s.append(c),o.append(s)}let s=()=>{let e={min:[],max:[]},t=!0;for(let n of a){let r=Number(n.input.value),i=n.input.value.trim()!==``&&Number.isFinite(r);n.input.setCustomValidity(i?``:`Enter a finite number.`),i||(t=!1),e[n.side][n.index]=r}for(let n=0;n<3;n+=1)e.min[n]>=e.max[n]&&(a.find(e=>e.index===n&&e.side===`max`).input.setCustomValidity(`Maximum must be greater than minimum.`),t=!1);t&&(X({type:`applySectionBox`,sectionBox:e}),l(e,!0),XC())};n.addEventListener(`change`,()=>{n.checked?s():(X({type:`applySectionBox`}),l(gi(Y.bounds),!1),XC())});for(let{input:e}of a)e.addEventListener(`change`,s);let c=document.createElement(`button`);c.type=`button`,c.textContent=`Reset section`,c.addEventListener(`click`,()=>{X({type:`applySectionBox`}),l(gi(Y.bounds),!1),XC()}),e.append(t,r,o,c),J.sectionBoxControls.append(e);function l(e,t){n.checked=t;for(let n of a)n.input.value=String(e[n.side][n.index]),n.input.disabled=!t,n.input.setCustomValidity(``)}}var QS=[{glyph:`ISO`,label:`Isometric`,view:`iso`},{glyph:`+X`,label:`Look down +X`,view:`positiveX`},{glyph:`+Z`,label:`Look down +Z`,view:`positiveZ`}],$S=[{glyph:`+`,label:`Zoom in`,zoom:1.25},{glyph:`−`,label:`Zoom out`,zoom:.8}];function eC(){J.cameraControls.replaceChildren();let e=e=>{let t=document.createElement(`div`);return t.className=`camera-group`,t.setAttribute(`role`,`group`),t.setAttribute(`aria-label`,e),t},t=e=>{let t=document.createElement(`button`);return t.type=`button`,t.textContent=e.glyph,t.setAttribute(`aria-label`,e.label),t.dataset.focusKey=`camera:${e.view??e.label}`,t.title=e.label,t.addEventListener(`click`,()=>e.view?ux?.setStandardView(e.view):ux?.zoomBy(e.zoom)),t},n=e(`Standard views`);for(let e of QS)n.append(t(e));let r=e(`Zoom`);for(let e of $S)r.append(t(e));J.cameraControls.append(n,r),J.resetView.textContent=`⤢`,J.resetView.title=`Reset view — fit the full scene`,J.resetView.setAttribute(`aria-label`,`Reset 3D view — fit the full scene`),J.cameraControls.append(J.resetView)}function tC(e){J.layerList.replaceChildren();let t=e.flatMap(e=>e.layerIds),n=t.filter(e=>Y.layers[e]?.visible!==!1).length;J.layerTally.textContent=t.length>0?`${n} of ${t.length}`:``;for(let t of e){let e=document.createElement(`section`),n=document.createElement(`h3`);n.textContent=t.label,e.append(n);for(let n of t.leaves)e.append(nC(n));for(let n of t.groups){let t=document.createElement(`details`),r=document.createElement(`summary`);r.textContent=`${n.label} (${n.leaves.length})`,t.append(r);for(let e of n.leaves)t.append(nC(e));e.append(t)}J.layerList.append(e)}}function nC(e){let t=Y.layers[e.layerId],n=document.createElement(`label`);n.className=`layer-toggle`;let r=document.createElement(`input`);return r.type=`checkbox`,r.checked=t?.visible!==!1,r.dataset.focusKey=`layer:${e.layerId}`,r.addEventListener(`change`,()=>{X({type:`setLayerVisibility`,layerId:e.layerId,visible:r.checked}),$()}),n.append(r,` ${e.label} (${e.count})`),n}function rC(){let e=Y.review?qy(Y.review).warningCount:0,t=(Y.issues??[]).length,n=[e>0?`${e} warning${e===1?``:`s`}`:null,t>0?`${t} issue${t===1?``:`s`}`:null].filter(Boolean);return n.length>0?n.join(`  ·  `):`0 issues`}function iC(){J.diagnosticList.replaceChildren(),J.diagnosticList.className=`diagnostics-workflow`;let e=Y.review?.tables?.diagnostics?.rows??Y.review?.diagnostics??[],t=Y.diagnostics??[],n=t.filter(aC),r=t.filter(e=>!aC(e)),i=[...Y.reviewDiagnostics??[],...n],a=(Y.review?.provenance??[]).map(e=>({severity:`info`,code:`PROVENANCE_${String(e.kind??`record`).toUpperCase()}`,source:e.solver_name??e.kind??`review package`,target:e.id??e.load_case??`review`,message:`${e.load_case?`Load case ${e.load_case}; `:``}${Object.keys(e.files??{}).length} linked artifact(s).`})),o=(Y.issues??[]).map(e=>({severity:e.severity??`warning`,code:e.id??`SCENE_ISSUE`,source:`scene issue`,target:(e.entity_ref??e.load_case??(e.object_ids??[]).join(`, `))||`scene`,message:e.title??e.message??`Scene issue without detail.`}));oC(`Review diagnostics`,e),oC(`Review provenance`,a),oC(`Scene diagnostics`,r),oC(`Scene issues`,o),oC(`Load and preview diagnostics`,i);let s=J.diagnosticList.childElementCount===0;J.diagnosticList.hidden=s;let c=J.diagnosticList.closest(`details`);c&&(c.hidden=s)}function aC(e){let t=String(e?.code??``).toLowerCase();return t.startsWith(`viewer.review.`)||t.includes(`preview`)}function oC(e,t){if(t.length===0)return;let n=document.createElement(`section`);n.className=`diagnostic-group`;let r=document.createElement(`h2`);r.textContent=`${e} (${t.length})`,n.append(r);for(let e of t){let t=document.createElement(`article`);t.className=`diagnostic-item`;let r=document.createElement(`span`);r.className=`severity-badge`,r.dataset.severity=String(e.severity??`info`).toLowerCase(),r.textContent=String(e.severity??`info`).toUpperCase();let i=document.createElement(`p`);i.textContent=e.message??`No detail supplied.`;let a=document.createElement(`dl`);sC(a,`Source`,e.source??`Not supplied`),sC(a,`Code`,e.code??`diagnostic`),sC(a,`Target`,e.target??`Not supplied`),t.append(r,i,a),n.append(t)}J.diagnosticList.append(n)}function sC(e,t,n){let r=document.createElement(`dt`);r.textContent=t;let i=document.createElement(`dd`);i.textContent=String(n),e.append(r,i)}var cC=[{id:`engineering`,label:`Engineering`},{id:`body`,label:`Body`},{id:`kind`,label:`Kind`},{id:`material`,label:`Material`},{id:`route`,label:`Route`},{id:`group`,label:`Group`},{id:`source`,label:`Source`}],lC={geometry:`Geometry`,analysis_mesh:`Analysis mesh`,subpoints:`Sub-points`,deformed:`Deformed mesh`,other:`Other (not a body)`},uC=`engineering`;function dC(){J.objectsSection.open=!0,$()}function fC(){J.searchInput.blur()}J.objectList.addEventListener(`keydown`,yC);function pC(){J.findDismiss.hidden=ix.trim()===``,J.findScope.replaceChildren();for(let e of cC){let t=document.createElement(`button`);t.type=`button`,t.className=`scope-chip`,t.dataset.findScopeId=e.id,t.dataset.focusKey=`scope:${e.id}`,t.setAttribute(`aria-pressed`,String(e.id===uC)),t.textContent=e.label,t.addEventListener(`click`,()=>{uC=e.id,$()}),J.findScope.append(t)}mC()}function mC(){J.objectList.replaceChildren();let e=si(Y,ix),t=new Map(e.map(e=>[e.object.id,e])),n=new Set(Y.visibleObjectIds??[]),r=new Set(h(Y,Y.selectedObjectIds??[])),i=ei(Y,{groupBy:uC}),a=0,o=0;for(let e of i.children){let i=e.objectIds.filter(e=>t.has(e));if(i.length===0)continue;let s=i.filter(e=>n.has(e)),c=i.filter(e=>!n.has(e));if(a+=s.length,o+=c.length,uC===`engineering`)if(e.id===`engineering:analysis`){J.objectList.append(bC({...e,objectIds:i},i.length,r));let a=document.createElement(`details`);a.className=`representation-list generated-list`,a.open=!!ix.trim();let o=document.createElement(`summary`);o.textContent=`${i.length} solver-generated object${i.length===1?``:`s`}`,a.append(o);for(let e of i)a.append(xC(t.get(e),n.has(e),r));J.objectList.append(a)}else{let a=i.find(t=>e.id===`engineering:${t}`)??s[0]??i[0];J.objectList.append(xC(t.get(a),n.has(a),r));let o=i.filter(e=>e!==a);if(o.length){let e=document.createElement(`details`);e.className=`representation-list`,e.open=!!ix.trim();let i=document.createElement(`summary`);i.textContent=`${o.length} representation${o.length===1?``:`s`}`,e.append(i);for(let i of o)e.append(xC(t.get(i),n.has(i),r));J.objectList.append(e)}}else{J.objectList.append(bC({...e,objectIds:i},i.length,r));for(let e of s)J.objectList.append(xC(t.get(e),!0,r))}uC!==`engineering`&&c.length>0&&J.objectList.append(SC(c,t))}a===0&&o===0&&J.objectList.append(iw(ix.trim()?`No object matches that.`:`This scene has no objects.`)),vC(),TC(a,o)}var hC=`button[data-object-id], .group-header`;function gC(e){for(let t=e;t&&t!==J.objectList;t=t.parentElement)if(t.tagName===`DETAILS`&&!t.open)return!1;return!0}function _C(){return[...J.objectList.querySelectorAll(hC)].filter(gC)}function vC(){let e=_C(),t=document.activeElement,n=t instanceof HTMLElement&&J.objectList.contains(t),r=e[0]??null;for(let t of e)t.tabIndex=-1;if(r&&(r.tabIndex=0),!n)return;let i=J.objectList.querySelector(`[data-object-id="${CSS.escape(t?.dataset?.objectId??``)}"]`);i instanceof HTMLElement&&gC(i)&&(r.tabIndex=-1,i.tabIndex=0)}function yC(e){if(e.defaultPrevented||!(e.target instanceof HTMLElement)||!e.target.closest(hC))return;let t=_C();if(t.length===0)return;let n=t.indexOf(e.target.closest(hC)),r=e.key===`ArrowDown`,i=e.key===`ArrowUp`,a={Home:0,End:t.length-1}[e.key];if(!r&&!i&&a===void 0)return;e.preventDefault();let o=a===void 0?n<0?0:Math.min(t.length-1,Math.max(0,n+(r?1:-1))):a;for(let e of t)e.tabIndex=-1;t[o].tabIndex=0,t[o].focus()}function bC(e,t,n){let r=document.createElement(`button`);r.type=`button`,r.className=`group-header`,r.dataset.groupId=e.id,r.dataset.focusKey=`group:${e.id}`;let i=document.createElement(`span`);i.textContent=uC===`body`?lC[e.label]??e.label:e.label;let a=document.createElement(`span`);return a.className=`group-count`,a.textContent=String(t),r.append(i,a),r.title=`Select every matching object in this group`,r.setAttribute(`aria-pressed`,String(e.objectIds.every(e=>n.has(e)))),r.addEventListener(`click`,()=>{X({type:`selectObjects`,objectIds:e.objectIds}),rx=Y.selectedObjectIds[0]??rx,$()}),r}function xC(e,t,n){let r=e.object,i=document.createElement(`button`);i.type=`button`,i.className=`object-row`,i.dataset.objectId=r.id,i.title=r.id,i.dataset.focusKey=`object:${r.id}`,i.setAttribute(`aria-label`,`${r.name||r.id} - ${r.kind}`);let a=n.has(r.id);i.classList.toggle(`selected`,a),i.setAttribute(`aria-pressed`,String(a)),t||i.classList.add(`not-drawn`);let o=wC(r.entity_ref),s=document.createElement(`span`);s.className=`object-name`,CC(s,r.name||r.id,e);let c=document.createElement(`span`);if(c.className=`object-meta`,o){let e=document.createElement(`span`);e.className=`object-ref`,e.textContent=o,c.append(e)}if(r.kind){let e=document.createElement(`span`);e.className=`object-kind`,e.textContent=r.kind,c.append(e)}if(i.append(s,c),e.field&&![`name`,`id`].includes(e.field)){let t=document.createElement(`span`);t.className=`match-chip`,t.textContent=`matched ${e.field}`,i.append(t)}return i.addEventListener(`click`,e=>{rx=r.id,X({type:`selectObject`,objectId:r.id,additive:e.shiftKey}),$()}),i}function SC(e,t){let n=document.createElement(`button`);return n.type=`button`,n.className=`hidden-reveal`,n.dataset.hiddenReveal=String(e.length),n.textContent=`${e.length} more hidden — show`,n.title=`These match but belong to a body that is switched off`,n.addEventListener(`click`,()=>{let t=new Set;for(let n of e)for(let e of Y.objectLayerIds?.[n]??[])t.add(e);for(let e of t)X({type:`setLayerVisibility`,layerId:e,visible:!0});$()}),n}function CC(e,t,n){if(!(n?.field===`name`&&n.start>=0&&n.end<=t.length)){e.textContent=t;return}e.append(document.createTextNode(t.slice(0,n.start)),Object.assign(document.createElement(`mark`),{textContent:t.slice(n.start,n.end)}),document.createTextNode(t.slice(n.end)))}function wC(e){return typeof e==`string`?e:e?.kind&&e?.id?`${e.kind}:${e.id}`:``}function TC(e=0,t=0){J.railUtility.replaceChildren();for(let[e,t]of[[`Fit selected`,`fitSelection`],[`Hide selected`,`hideSelected`],[`Isolate selected`,`isolateSelection`]]){let n=document.createElement(`button`);n.type=`button`,n.className=`utility-button`,n.textContent=e,n.disabled=!Y.selectedObjectIds?.length,n.addEventListener(`click`,()=>{X({type:t}),$()}),J.railUtility.append(n)}let n=document.createElement(`button`);n.type=`button`,n.className=`utility-button`,n.dataset.measure=``,n.textContent=yx?`Cancel measure`:`Measure two points`,n.setAttribute(`aria-pressed`,String(yx)),n.addEventListener(`click`,()=>{yx=!yx,bx=[],$()}),J.railUtility.append(n);let r=document.createElement(`div`);r.className=`measurement-readout`,r.setAttribute(`role`,`status`);let i=O(Y),a=bx.map(({point:e},t)=>`P${t+1} (${e.map(e=>N(e,`m`,i)).join(`, `)})`);r.textContent=bx.length===2?`${a.join(` · `)} · Distance ${N(Jy(bx[0].point,bx[1].point),`m`,i)}`:yx?`${a.join(` · `)}${a.length?` · `:``}Click ${a.length?`second`:`first`} point on visible geometry.`:``,J.railUtility.append(r);for(let[e,t]of[[`section`,`Section box`],[`views`,`Saved views`]]){let n=document.createElement(`button`);n.type=`button`,n.className=`utility-button`,n.dataset.railTool=e,n.dataset.focusKey=`tool:${e}`,n.setAttribute(`aria-expanded`,String(EC===e)),n.textContent=t,n.addEventListener(`click`,()=>{EC=EC===e?null:e,$()}),J.railUtility.append(n)}J.findTally.textContent=t>0?`${e} drawn / ${t} hidden`:`${e} objects`}var EC=null,DC=new Set,OC=!1,kC=!1;function AC(){if(J.railPopover.hidden=EC===null,!J.railPopover.hidden)for(let[e,t]of[[`section`,J.sectionBoxControls],[`views`,J.savedViews]])t&&(t.hidden=e!==EC)}function jC(e,{focusKey:t=null}={}){let n=document.createElement(`button`);n.type=`button`,n.className=e.id===Y.activeIssueId?`selected`:``,t&&(n.dataset.focusKey=t);let r=document.createElement(`span`);r.className=`issue-severity issue-severity-${e.severity??`warning`}`,r.textContent=String(e.severity??`warning`).toUpperCase();let i=document.createElement(`span`);i.className=`issue-title`,i.textContent=e.title??e.id,n.append(r,i);let a=ui(Y,e);if(a>0){let e=document.createElement(`span`);e.className=`issue-magnitude`,e.textContent=`${N(a,`m`,O(Y))} overlap`,e.title=`Overlap depth - the list is ordered worst first`,n.append(e)}let o=$v(Y,e.id);if(o){let e=document.createElement(`span`);e.className=`issue-disposition-chip disposition-${o.status}`,e.textContent=Hv(o.status)?.label??o.status,e.title=o.author?`${o.status} by ${o.author}${o.at?` on ${o.at.slice(0,10)}`:``}`:o.status,n.append(e)}return n.addEventListener(`click`,()=>{X({type:`focusIssue`,issueId:e.id}),rx=Y.selectedObjectIds.map(e=>Y.objects.find(t=>t.id===e)).find(e=>e?.kind===`clash_marker`)?.id??Y.selectedObjectIds[0]??null,$()}),n}var MC=25;function NC(e,t,n=J.issueList){let r=document.createElement(`div`);r.className=`issue-group-head`;let i=document.createElement(`span`);i.className=`issue-severity issue-severity-${e.severity}`,i.textContent=e.severity.toUpperCase();let a=document.createElement(`span`);a.className=`issue-group-case`,a.textContent=e.loadCase===`no_load_case`?`no load case`:`case ${e.loadCase}`;let o=document.createElement(`span`);o.className=`issue-group-count`;let s=e.issues[0]?ui(Y,e.issues[0]):0;o.textContent=s>0?`${e.total} · worst ${N(s,`m`,O(Y))}`:`${e.total}`,o.title=`Issues in this group, and the deepest overlap among them`,r.append(i,a,o);let c=PC(e.issues);if(c){let t=document.createElement(`p`);t.className=`issue-group-culprit`,t.textContent=`${e.total} involving ${c}`,r.append(t)}n.append(r);let l=e.issues.slice(0,MC);for(let e of l)n.append(t(e));if(e.issues.length>l.length){let r=document.createElement(`details`);r.className=`issue-overflow`;let i=document.createElement(`summary`);i.textContent=`${e.issues.length-l.length} more, less severe`,r.append(i);for(let n of e.issues.slice(MC))r.append(t(n));n.append(r)}}function PC(e){let t=new Map;for(let n of e)for(let e of di(Y,n))t.set(e,(t.get(e)??0)+1);let n=null,r=0;for(let[e,i]of t)i>r&&(n=e,r=i);return r>=3&&r>=e.length*.5?n:null}function FC(){J.issueList.replaceChildren();let e=document.createElement(`label`),t=document.createElement(`input`);t.type=`checkbox`,t.checked=ax.operatingOnly,t.dataset.focusKey=`issue-filter`,t.addEventListener(`change`,()=>{ax={...ax,operatingOnly:t.checked},FC()}),e.append(t,` Operating-only`),J.issueList.append(e);let n=fi(Y,ax);if(n.length===0){let e=document.createElement(`div`);e.className=`meta`,e.textContent=`No issues.`,J.issueList.append(e),J.issueList.append(IC());return}for(let e of n)NC(e,e=>jC(e,{focusKey:`issue:${e.id}`}));J.issueList.append(IC())}function IC(){let e=document.createElement(`div`);e.className=`review-record-export`;let n=ey(Y),r=document.createElement(`p`);if(r.className=`review-record-summary`,n.touched===0)return r.textContent=`No dispositions recorded. Open an issue to record a decision.`,e.append(r),e;if(r.textContent=`${Vv.filter(e=>n[e.id]>0).map(e=>`${n[e.id]} ${e.label.toLowerCase()}`).join(` · `)} of ${(Y.issues??[]).length} issues.`,e.append(r),!Y.reviewerName){let t=document.createElement(`p`);t.className=`review-record-author`,t.textContent=`No reviewer name set, so the exported record is unattributed.`,e.append(t)}let i=document.createElement(`button`);i.type=`button`,i.className=`bar-button`,i.dataset.focusKey=`review-record-csv`,i.textContent=`Export record (CSV)`,i.title=`One row per disposition, with the reviewer, the timestamp and the reason`,i.addEventListener(`click`,()=>{let e=ty(Y,{at:new Date().toISOString()});t(new Blob([ay(e)],{type:`text/csv;charset=utf-8`}),`review-dispositions.csv`)});let a=document.createElement(`button`);return a.type=`button`,a.className=`bar-button`,a.dataset.focusKey=`review-record-json`,a.textContent=`Export record (JSON)`,a.title=`The same record with the full transition history`,a.addEventListener(`click`,()=>{let e=ty(Y,{at:new Date().toISOString()});t(new Blob([JSON.stringify(e,null,2)],{type:`application/json;charset=utf-8`}),`review-record.json`)}),e.append(i,a),e}function LC(){J.buildIssues.replaceChildren();let e=Dw()?Y.issues??[]:[];if(J.buildIssues.hidden=e.length===0,e.length===0)return;let t=fi(Y,{}),n=e.length,r=document.createElement(`h2`),i=e.reduce((e,t)=>Math.max(e,ui(Y,t)),0);r.textContent=i>0?`Model issues (${n} · deepest ${N(i,`m`,O(Y))})`:`Model issues (${n})`,J.buildIssues.append(r);for(let e of t)NC(e,e=>jC(e,{focusKey:`build-issue:${e.id}`}),J.buildIssues)}function RC(){Z.linesMoved=Jw();let e=Hb(Y,rx);J.propertyActions.replaceChildren(),J.properties.replaceChildren();let t=Y.activeIssueId?mi(Y,Y.activeIssueId):null;if(J.inspector.hidden=!e&&!t,!e){if(t)J.properties.append(WC({title:`Issue`,rows:t}));else{let e=document.createElement(`div`);e.className=`meta`,e.textContent=`Select an object.`,J.properties.append(e)}return}let n=e.sections,r=Y.objects.find(e=>e.id===rx);if(r?.entity_ref&&Y.selectedObjectIds.length===1){let e=document.createElement(`button`);e.type=`button`,e.textContent=`Copy Entity Ref`,e.dataset.focusKey=`action:copy`,e.addEventListener(`click`,()=>{let e=navigator.clipboard?.writeText(r.entity_ref);if(!e){ew(`Clipboard unavailable in this browser - select the value to copy it`,!0);return}e.then(()=>ew(`Copied ${r.entity_ref}`),()=>ew(`Could not copy - select the value to copy it`,!0))}),J.propertyActions.append(e)}let i=document.createElement(`button`);i.type=`button`,i.textContent=`Fit selected`,i.dataset.focusKey=`action:fit`,i.addEventListener(`click`,()=>{X({type:`fitSelection`}),$()});let a=document.createElement(`button`);a.type=`button`,a.textContent=`Hide selected`,a.dataset.focusKey=`action:hide`,a.addEventListener(`click`,()=>{X({type:`hideSelected`}),$()});let o=document.createElement(`button`);o.type=`button`,o.textContent=`Isolate selected`,o.dataset.focusKey=`action:isolate`,o.addEventListener(`click`,()=>{X({type:`isolateSelection`}),$()}),J.propertyActions.append(i,a,o,YC());let s=gS();s&&J.propertyActions.append(s);let c=document.createElement(`button`);if(c.type=`button`,c.textContent=`Clear selection`,c.dataset.focusKey=`action:clear`,c.addEventListener(`click`,()=>{X({type:`selectObjects`,objectIds:[]}),$()}),J.propertyActions.append(c),(Y.selectedObjectIds??[]).length>1){let e=Y.selectedObjectIds.map(e=>Y.objects.find(t=>t.id===e)).filter(Boolean),t=[...new Set(e.flatMap(e=>e.group_ids??e.metadata?.groups??[]))];J.properties.append(zC({title:`${e.length} objects selected`,lede:t.length?`Groups: ${t.join(`, `)}`:`Multiple objects`,meta:`Fit, hide and isolate apply to the whole selection.`}));for(let t of e){let e=document.createElement(`button`);e.type=`button`,e.textContent=t.name||t.id,e.addEventListener(`click`,()=>{X({type:`selectObject`,objectId:t.id}),$()}),J.properties.append(e)}return}J.properties.append(zC(e)),Dw()&&(/^(element|support):/.test(r?.entity_ref??``)||r?.kind===`applied_load`)&&J.properties.append(sT(r)),e.dofs&&J.properties.append(VC(e.dofs,e.restraintLine));for(let e of n)J.properties.append(HC(e));let l=Y.selectedObjectIds.length===1?de(Y,r):null;l&&J.properties.append(HC(l)),t&&(J.properties.append(WC({title:`Issue`,rows:t})),J.properties.append(KC({kind:`issue`,subjectId:t.id})));let u=Tn(Y,X,$,`selection`,rx);u&&J.properties.append(u),Object.keys(e.reference).length>0&&J.properties.append(UC(e.reference))}function zC(e){let t=document.createElement(`div`);t.className=`evidence-head`;let n=document.createElement(`div`);n.className=`evidence-title-row`;let r=document.createElement(`div`);if(r.className=`evidence-title`,r.textContent=e.title,n.append(r),e.badge){let t=document.createElement(`span`);t.className=`evidence-badge`,t.textContent=e.badge,n.append(t)}if(t.append(n),e.lede){let n=document.createElement(`p`);n.className=`evidence-lede`,n.textContent=e.lede,t.append(n)}if(e.meta){let n=document.createElement(`div`);n.className=`evidence-meta`,n.textContent=e.meta,t.append(n)}return t}var BC=Object.freeze({spring:`M1 5h1.6l1.6-3.4 2.4 6.8 2.4-6.8L10.6 5H13`,"one-way":`M6 1.5l4 6H2z M0.5 9.5h11`});function VC(e,t){let n=document.createElement(`section`);n.className=`property-section`;let r=document.createElement(`h3`);r.textContent=`Restraint`;let i=uT(t);i&&r.append(i);let a=document.createElement(`div`);a.className=`restraint-strip`;for(let t of e){let e=document.createElement(`div`);e.className=`restraint-dof`;let n=document.createElement(`div`);n.className=`restraint-cell is-${t.state.replace(/\s+/g,`-`)}`;let r=document.createElement(`span`);r.textContent=t.axis,n.append(r);let i=BC[t.state];if(i){let e=document.createElementNS(`http://www.w3.org/2000/svg`,`svg`);e.setAttribute(`viewBox`,`0 0 14 11`),e.setAttribute(`width`,`14`),e.setAttribute(`height`,`11`),e.setAttribute(`fill`,`none`),e.setAttribute(`stroke`,`currentColor`),e.setAttribute(`stroke-width`,`1.3`),e.setAttribute(`stroke-linejoin`,`round`),e.setAttribute(`aria-hidden`,`true`);let t=document.createElementNS(`http://www.w3.org/2000/svg`,`path`);t.setAttribute(`d`,i),e.append(t),n.append(e)}let o=document.createElement(`div`);o.className=`restraint-word is-${t.state.replace(/\s+/g,`-`)}`,o.textContent=t.state,e.setAttribute(`role`,`group`),e.setAttribute(`aria-label`,`${t.axis} ${t.state}`),e.append(n,o),a.append(e)}return n.append(r,a),n}function HC(e){let t=document.createElement(`section`);t.className=`property-section`;let n=document.createElement(`h3`);n.textContent=e.title;let r=uT(e.sourceLine);r&&n.append(r),t.append(n);let i=document.createElement(`table`);i.className=`property-table`;let a=document.createElement(`tbody`);for(let t of e.lines){if(t.kind===`note`)continue;let e=document.createElement(`tr`),n=document.createElement(`th`);n.scope=`row`,n.textContent=t.label;let r=document.createElement(`td`);r.textContent=GC(t.value);let i=uT(t.sourceLine);i&&r.append(i),e.append(n,r),a.append(e)}i.append(a),t.append(i);for(let n of e.lines.filter(e=>e.kind===`note`)){let e=document.createElement(`p`);e.className=`evidence-note`,e.textContent=n.label,t.append(e)}return t}function UC(e){let t=document.createElement(`details`);t.className=`evidence-reference`;let n=document.createElement(`summary`);return n.textContent=`Reference`,t.append(n),t.append(WC({title:``,rows:e})),t}function WC(e){let t=document.createElement(`section`);t.className=`property-section`;let n=document.createElement(`h3`);n.textContent=e.title,n.hidden=!e.title;let r=document.createElement(`table`);r.className=`property-table`;let i=document.createElement(`tbody`);for(let[t,n]of Object.entries(e.rows??{})){let e=document.createElement(`tr`),r=document.createElement(`th`);r.scope=`row`,r.textContent=t;let a=document.createElement(`td`);a.textContent=GC(n),e.append(r,a),i.append(e)}return r.append(i),t.append(n,r),t}function GC(e){return Array.isArray(e)||e&&typeof e==`object`?JSON.stringify(e):String(e)}function KC(e){let t=document.createElement(`section`);t.className=`issue-disposition`;let n=document.createElement(`h3`);return n.textContent=e.kind===`finding`?`Disposition — finding`:`Disposition`,t.append(n),e.address&&t.append(iw(qC(e.address))),t.append(...JC(e)),t}function qC(e){let t=[];t.push(e.element_id??e.object_id??`unknown element`);let n=[e.field,e.component].filter(Boolean).join(` / `);n&&t.push(n),t.push(e.load_case??e.result_state_id??`unknown case`);let r=t.join(` — `);if(!Number.isFinite(Number(e.value)))return r;let i=O(Y);return`${r}: ${N(e.value,e.unit??``,i)}${Number.isFinite(Number(e.utilization))?` · u=${yw(e.utilization)}`:``}`}function JC(e){let t=$v(Y,e.subjectId),n=t?.status??`open`,r=document.createElement(`input`);r.type=`text`,r.className=`issue-reviewer`,r.placeholder=`Reviewer name`,r.value=Y.reviewerName??``,r.setAttribute(`aria-label`,`Reviewer name (self-declared)`),r.dataset.focusKey=`issue-reviewer`,r.addEventListener(`change`,()=>{X({type:`setReviewerName`,name:r.value}),$()});let i=document.createElement(`select`);i.setAttribute(`aria-label`,`Issue Status`),i.dataset.focusKey=`issue-status`;for(let e of Vv){let t=document.createElement(`option`);t.value=e.id,t.textContent=e.label,t.title=e.description,t.selected=e.id===n,i.append(t)}let a=document.createElement(`textarea`);a.setAttribute(`aria-label`,`Issue Comment`),a.dataset.focusKey=`issue-comment`,a.placeholder=t?.status===`waived`||n===`waived`?`What is being waived, and why`:`Note (optional)`,a.value=t?.comment??``;let o=document.createElement(`p`);o.className=`issue-refusal`,o.setAttribute(`role`,`status`),o.hidden=!0;let s=()=>{let t=Wv({status:i.value,comment:a.value});o.hidden=!t,o.textContent=t??``,!t&&(X({type:`recordDisposition`,subjectId:e.subjectId,address:e.address,status:i.value,comment:a.value,at:new Date().toISOString()}),$())};i.addEventListener(`change`,s),a.addEventListener(`change`,s);let c=[r,i,a,o];if(t&&t.transitions.length>0){let e=document.createElement(`p`);e.className=`issue-history`,e.textContent=`${t.transitions.length} recorded change${t.transitions.length===1?``:`s`}, last by ${t.author??`an unnamed reviewer`}`,t.at&&(e.textContent+=` on ${t.at.slice(0,10)}`),e.title=t.transitions.map(e=>`${e.at??`?`} ${e.status}${e.comment?` — ${e.comment}`:``}`).join(`
`),c.push(e)}return c}function YC(){let e=document.createElement(`button`);return e.type=`button`,e.textContent=`Restore view`,e.dataset.focusKey=`issue-restore`,e.addEventListener(`click`,()=>{X({type:`restoreVisibility`}),$()}),e}function XC(){if(dx){ew(`Results ready · 3D unavailable`,!0);return}try{ux??=r_(J.canvas)}catch(e){if(e?.code!==`viewer.webgl2_unavailable`)throw e;dx=!0,ZC(),ew(`Results ready · 3D unavailable`,!0);return}eC();let e=ux.render(Y),t=e;S_(e,px),px&&ux.redraw(),fx=t;let n=[...new Set(t.renderableObjects.filter(e=>e.visible!==!1).flatMap(e=>e.userData.objectIds??[]))];globalThis.__tubaViewer={bootId:xx,state:Y,lastRender:{diagnostics:t.diagnostics,objectIds:n,renderableCount:t.renderableObjects.length},resultReview:{hotspots:kt(Y),legend:Et(Y)}},t.diagnostics.length>0?ew(`Ready with ${t.diagnostics.length} render warning(s)`,`warn`):ew(`Ready`)}function ZC(){J.viewport.dataset.renderer=`unavailable`;let e=document.createElement(`section`);e.className=`viewport-unavailable`,e.dataset.viewportUnavailable=``,e.setAttribute(`aria-label`,`3D view unavailable`);let t=document.createElement(`h2`);t.textContent=`3D view unavailable`;let n=document.createElement(`p`);n.textContent=`This browser could not start WebGL2. The review report carries the processed result tables.`;let r=document.createElement(`p`);r.textContent=`Try a current browser with graphics acceleration enabled, then reload this review.`,e.append(t,n,r),J.viewport.append(e)}var QC=Math.PI/24,$C={ArrowLeft:()=>ux?.orbitBy(-QC,0),ArrowRight:()=>ux?.orbitBy(QC,0),ArrowUp:()=>ux?.orbitBy(0,-QC),ArrowDown:()=>ux?.orbitBy(0,QC),"+":()=>ux?.zoomBy(1.25),"=":()=>ux?.zoomBy(1.25),"-":()=>ux?.zoomBy(.8),_:()=>ux?.zoomBy(.8),Home:()=>ux?.resetView(),0:()=>ux?.resetView(),x:()=>ux?.setStandardView(`positiveX`),X:()=>ux?.setStandardView(`negativeX`),y:()=>ux?.setStandardView(`positiveY`),Y:()=>ux?.setStandardView(`negativeY`),z:()=>ux?.setStandardView(`positiveZ`),Z:()=>ux?.setStandardView(`negativeZ`),i:()=>ux?.setStandardView(`iso`),I:()=>ux?.setStandardView(`iso`)};J.canvas.addEventListener(`keydown`,e=>{if(e.ctrlKey||e.metaKey||e.altKey)return;let t=$C[e.key];t&&(e.preventDefault(),t())}),J.canvas.addEventListener(`click`,e=>{if(vx){vx=!1;return}if(!Y||ux?.handleGizmoClick(e))return;let t=J.canvas.getBoundingClientRect(),n={x:e.clientX-t.left,y:e.clientY-t.top};if(yx){let e=d_(fx,n,{width:t.width,height:t.height});e&&(bx.push(e),bx.length===2&&(yx=!1),$());return}let r=u_(fx,n,{width:t.width,height:t.height});r&&(rx=r,X({type:`selectObject`,objectId:r,additive:e.shiftKey}),$())}),J.resetView.addEventListener(`click`,()=>ux?.resetView()),J.bodyLegendToggle.addEventListener(`click`,()=>{kC=!kC,$()}),J.displayPalette.addEventListener(`keydown`,e=>{e.key!==`Escape`||!J.displayPalette.open||(e.preventDefault(),J.displayPalette.open=!1,J.displayPalette.querySelector(`summary`).focus())}),document.addEventListener(`pointerdown`,e=>{J.displayPalette.contains(e.target)||(J.displayPalette.open=!1)}),J.canvas.addEventListener(`pointerdown`,e=>{gx=!0,_x={x:e.clientX,y:e.clientY},vx=!1,hx=null}),J.canvas.addEventListener(`pointermove`,e=>{if(!_x)return;let t=e.clientX-_x.x,n=e.clientY-_x.y;t*t+n*n>lx**2&&(vx=!0)}),globalThis.addEventListener(`pointerup`,()=>{gx=!1,_x=null}),globalThis.addEventListener(`pointercancel`,()=>{gx=!1,_x=null,vx=!1}),J.canvas.addEventListener(`mousemove`,e=>{gx||!Y||!fx||(hx={x:e.clientX,y:e.clientY},mx===null&&(mx=requestAnimationFrame(function e(){if(mx=null,gx||!hx||!fx)return;if(performance.now()-cx<32){mx=requestAnimationFrame(e);return}cx=performance.now();let t=J.canvas.getBoundingClientRect(),n=u_(fx,{x:hx.x-t.left,y:hx.y-t.top},{width:t.width,height:t.height});hx=null,n!==px&&(px=n,J.canvas.dataset.hoverObjectId=n??``,S_(fx,n),ux.redraw())})))}),J.canvas.addEventListener(`mouseleave`,()=>{hx=null,px!==null&&(px=null,J.canvas.dataset.hoverObjectId=``,fx&&S_(fx,null),ux?.redraw())});function ew(e,t=!1){let n=t===!0?`error`:t||`ok`;J.status.textContent===e&&J.status.dataset.level===n||(J.status.textContent=e,J.status.dataset.level=n,J.status.dataset.error=String(n===`error`),J.status.dataset.ready=String(n===`ok`&&e===`Ready`))}function tw(e,t=``){let{message:n,detail:r}=kx(e,t);if(r){let e=J.sceneMeta??J.appShell.querySelector(`[data-scene-meta]`);if(e){let t=document.createElement(`pre`);t.className=`status-detail`,t.textContent=r,e.append(t)}}ew(n,!0)}function nw(e){let t=new WebSocket(e);t.addEventListener(`open`,()=>ew(`Live preview connected`)),t.addEventListener(`message`,e=>{rw(e.data)}),t.addEventListener(`error`,()=>ew(`Live preview connection failed`,!0)),t.addEventListener(`close`,()=>{Y&&ew(`Live preview disconnected`,!0)})}async function rw(e){let t;try{t=JSON.parse(e)}catch{ew(`Live preview sent invalid JSON`,!0);return}if(t.type===`script_error`){Z.available&&$w(t);return}if([`solve_started`,`solve_failed`,`solve_finished`,`review_ready`,`review_failed`].includes(t.type)){await Ww(t);return}if(t.type===`scene_reloaded`){if(t.bundle&&(Z.reviewStale=!!t.review_stale,t.bundle===`build`&&Rw(),n(Qb)!==t.bundle)){await eT(),$();return}let e=t.bundle??t.bundle_url??Qb;Qb=e;try{await Px(e,{preserve:!0}),await eT(),$(),ew(Z.available?`Ready`:`Preview reloaded`)}catch(e){tw(e,`The rebuilt model could not be reloaded.`)}return}}function iw(e){let t=document.createElement(`div`);return t.className=`meta`,t.textContent=e,t}function aw(e,t=``){let n=document.createElement(`div`);n.className=`rail-group`;let r=document.createElement(`h2`);if(r.textContent=e,n.append(r),t){let e=document.createElement(`span`);e.className=`rail-group-state`,e.textContent=t,n.append(e)}return n}function ow(e,t){let n=t.tagName===`SELECT`||t.tagName===`INPUT`,r=document.createElement(n?`label`:`div`);r.className=`prow`;let i=document.createElement(`span`);return i.className=`pname`,i.textContent=e,n&&sw(t,e),r.append(i,t),r}function sw(e,t){e.dataset.focusKey=`bar:${t}`}function cw(e,t,n){let r=document.createElement(`select`);for(let n of t){let t=typeof n==`string`?{id:n,label:n}:n,i=document.createElement(`option`);i.value=t.id,i.textContent=t.label,i.selected=t.id===e,r.append(i)}return r.title=r.options[r.selectedIndex]?.textContent??``,r.addEventListener(`change`,()=>n(r.value)),r}function lw(e){let t=document.createElementNS(`http://www.w3.org/2000/svg`,`svg`);t.setAttribute(`width`,`8`),t.setAttribute(`height`,`9`),t.setAttribute(`viewBox`,`0 0 8 9`),t.setAttribute(`aria-hidden`,`true`),t.setAttribute(`focusable`,`false`);for(let n of e===`pause`?[{x:`0`,width:`3`},{x:`5`,width:`3`}]:[]){let e=document.createElementNS(`http://www.w3.org/2000/svg`,`rect`);e.setAttribute(`x`,n.x),e.setAttribute(`y`,`0`),e.setAttribute(`width`,n.width),e.setAttribute(`height`,`9`),e.setAttribute(`fill`,`currentColor`),t.append(e)}if(e===`play`){let e=document.createElementNS(`http://www.w3.org/2000/svg`,`path`);e.setAttribute(`d`,`M0 0l8 4.5L0 9z`),e.setAttribute(`fill`,`currentColor`),t.append(e)}return t}function uw(e){return`#${Number(e).toString(16).padStart(6,`0`)}`}function dw(e){let t=Number(e)*100;return Number.isFinite(t)?`${t>=1?t.toFixed(0):t.toFixed(2)}%`:``}var fw=.003,pw=null;function mw(){if(pw){hw(),$();return}let e=Vt(Y);e>1&&(pw={base:e,frameId:null,startedAt:null},ux?.setDeformationInteraction(!0),pw.frameId=requestAnimationFrame(gw),$())}function hw(){if(!pw)return;let{base:e,frameId:t}=pw;t!==null&&cancelAnimationFrame(t),pw=null,ux?.setDeformationInteraction(!1),X({type:`setVisualDeformationScale`,scale:e})}function gw(e=0){if(!pw)return;pw.frameId=requestAnimationFrame(gw),pw.startedAt??=e;let t=(e-pw.startedAt)*fw,n=(1-Math.cos(t))/2;X({type:`setVisualDeformationScale`,scale:1+(pw.base-1)*n}),ux?.renderDeformation(Y)||XC()}globalThis.addEventListener(`beforeunload`,hw);function _w(e,t,n,r,i=e){let a=document.createElement(`label`),o=document.createElement(`input`);return o.type=`number`,o.min=`0`,o.step=n,o.value=String(t),sw(o,i),o.addEventListener(`change`,()=>r(o.value)),a.append(e,o),a}function vw(e,t,n,r,i,a,o=e){let s=document.createElement(`label`),c=document.createElement(`input`);return c.type=`range`,c.min=String(n),c.max=String(r),c.step=String(i),c.value=String(t),sw(c,o),c.addEventListener(`change`,()=>a(c.value)),s.append(e,c),s}function yw(e){let t=Number(e);return Number.isFinite(t)?String(Math.round(t*1e3)/1e3):`1`}J.searchInput.addEventListener(`input`,()=>{ix=J.searchInput.value,dC()}),J.searchInput.addEventListener(`focus`,dC),J.findDismiss.addEventListener(`click`,()=>{ix=``,J.searchInput.value=``,fC(),$()}),J.searchInput.addEventListener(`keydown`,e=>{if(e.key===`Escape`){if(ix.trim()){ix=``,J.searchInput.value=``,$();return}fC()}}),J.railToggle.addEventListener(`click`,()=>{ox=!ox,Lx()});function bw(e){let t=[`127.0.0.1`,`localhost`,`[::1]`].includes(window.location.hostname);return!Xb.embed&&!!(Xb.previewWebSocketUrl||t&&e.length===0)}async function xw(e){try{let t=await fetch(e,{cache:`no-store`});return t.ok?await t.json():null}catch{return null}}async function Sw(e){if(!bw(e))return!1;let t=await xw(`/api/project`);return t?.ok?(Z.project=t,Z.hasReview=!!t.has_review,Z.reviewStale=!!t.review_stale,Z.solving=!!t.solving,Z.preparing=!!t.preparing_review,!0):!1}async function Cw(e){if(!bw(e))return;let t=await xw(`/api/script`);if(typeof t?.code!=`string`)return;Z.available=!0;let n=qe(Z);qw(t.code),await Kw(n),X({type:`setStage`,stage:n}),$()}function ww(){return`${window.location.protocol===`https:`?`wss:`:`ws:`}//${window.location.host}/preview/ws`}function Tw(){return Ke(Y??{},{railExpanded:ox})}function Ew(){return Tw().stage}function Dw(){return Tw().stage===`build`}async function Ow(e){kw();let t=C(Zb?.scene,Zb?.review);if(!t)return;let n=String(e).replace(/\/+$/,``),r;try{r=await Aw(n,t.scriptUri)}catch{return}Q.available=!0,Q.baseUrl=n,Q.scriptUri=t.scriptUri,Q.loadCases=t.loadCases,Q.text.set(t.scriptUri,r),qw(r);let i=Sx.get(n);i&&(J.codeText.value=i.code,tT()),nT()}function kw(){Q.preview=null,Z.available||(Z.error=null,J.codeProblem.hidden=!0),Q.available=!1,Q.baseUrl=`.`,Q.scriptUri=null,Q.loadCases=[],Q.text.clear(),Z.available||(Z.codeTab=null)}async function Aw(e,t){let n=await fetch(`${e}/${t}`,{cache:`no-store`});if(!n.ok)throw Error(`Failed to load ${t}: ${n.status} ${n.statusText}`);if((n.headers?.get?.(`content-type`)??``).toLowerCase().includes(`text/html`))throw Error(`Expected text from ${t}, but received HTML.`);return n.text()}function jw(){let e=Tw();document.body.dataset.studio=String(Z.available),document.body.dataset.mode=e.stage===`build`?`build`:`review`,_T(),J.modeSwitch.hidden=!(Z.available||Q.available)||Y.embed;for(let e of J.modeSwitch.querySelectorAll(`[data-mode]`))e.setAttribute(`aria-pressed`,String(e.dataset.mode===document.body.dataset.mode));J.codePane.hidden=!e.scriptVisible,J.codeText.readOnly=!(Z.available||Q.available),Pw(),Mw(),zw(),nT()}function Mw(){if(!J.codeMeshToggle)return;let e=kr(Y).find(e=>e.id===`analysis_mesh`);if(!e){J.codeMeshToggle.hidden=!0;return}J.codeMeshToggle.hidden=!1;let t=e.visible;J.codeMeshToggle.setAttribute(`aria-pressed`,String(t)),J.codeMeshToggle.title=t?`Hide 1D analysis mesh (Alt+M)`:`Show 1D analysis mesh elements and nodes (Alt+M)`}function Nw(){return Z.available?Z.project?.load_cases??[]:Q.loadCases.map(e=>e.name)}function Pw(){let e=Nw();e.includes(Z.codeTab)||(Z.codeTab=null);let{codeTab:t}=Z,n=Y.activeLoadCase??e[0]??null,r=[...new Set([...dt(Y).map(e=>e.id),...e])],i=JSON.stringify([Z.available,r,n]);if(J.codeTabs.dataset.cases!==i||!J.codeTabs.children.length){J.codeTabs.dataset.cases=i;let t=Iw(null,`model.py`,`source`,`Edit load cases and local fields in Python`);J.codeTabs.replaceChildren(t),n&&e.includes(n)&&J.codeTabs.append(Iw(n,`Solver .comm`,`generated`,`${n}.comm — read-only Code_Aster input for the selected case`)),J.codeCase.replaceChildren(...r.map(e=>new Option(e,e)))}J.codeCase.value=n??``,J.codeCase.parentElement.parentElement.hidden=r.length===0;for(let e of J.codeTabs.children)e.setAttribute(`aria-pressed`,String((e.dataset.codeTab||null)===t));J.codeGutter.hidden=t!==null,J.codeText.parentElement.hidden=t!==null,J.commText.hidden=t===null,J.codeRun.hidden=!(Z.available||Q.available)||t!==null,Z.available||(J.codeRun.textContent=Cx?`Stop`:`Update geometry`,J.codeRun.title=Cx?`Stop the browser preview`:`Run Python in your browser (Ctrl+Enter)`),J.codeReset.hidden=Z.available||!Q.available,J.codeDownload.hidden=Z.available||!Q.available,t===null?Z.available?J.codeState.textContent===`Read-only`&&(J.codeState.textContent=`Python`):J.codeState.textContent=Cx?wx:Q.preview?J.codeText.value===Q.preview.code?`Geometry preview`:`Edited · run to update`:Tx()?`Edited draft`:`Python`:J.codeState.textContent=`Read-only`}function Fw(){let e=ce(Y).find(e=>e.load_case===Y.activeLoadCase);J.codeInputs.hidden=!e,J.reviewInputs.parentElement.hidden=!e,J.inputCount.textContent=e?`(${e.fields?.length??e.field_count??0} local)`:``;let t=ft(Y).some(e=>e.loadCase===Y.activeLoadCase);J.codeCaseStatus.textContent=Z.reviewStale||Tx()?`Review outdated`:t?`Solved result`:`Model inputs`,!Z.available&&Q.preview&&Dw()&&(J.codeCaseStatus.textContent=`Geometry only · not solved`);for(let[e,t]of[[J.buildInputs,J.compareCases.checked],[J.reviewInputs,!1]])fe(e,Y,{compare:t,select:e=>{X({type:`selectObjects`,objectIds:e}),$()},sourceLink:uT})}J.codeCase.addEventListener(`change`,()=>{X({type:`setActiveLoadCase`,loadCase:J.codeCase.value}),$()}),J.compareCases.addEventListener(`change`,Fw);function Iw(e,t,n,r){let i=document.createElement(`button`);i.type=`button`,i.className=`code-file`,i.dataset.codeTab=e??``,i.title=r;let a=document.createElement(`span`);return a.className=`code-role code-role-${n}`,a.textContent=n,i.append(t,a),i.addEventListener(`click`,()=>Lw(e)),i}function Lw(e){Z.codeTab!==e&&(e!==null&&Y.activeLoadCase!==e&&X({type:`setActiveLoadCase`,loadCase:e}),Z.codeTab=e,Pw(),nT(),e===null?iT():(J.commText.textContent=Z.available?`Generating…`:`Loading…`,Rw()))}async function Rw(){let e=Z.codeTab;if(e===null)return;let t=++Z.commRequest,n;if(Z.available)try{let t=await fetch(`/api/comm?case=${encodeURIComponent(e)}`,{cache:`no-store`});n=await t.json().catch(()=>({error:`Studio answered ${t.status}`}))}catch(e){n={error:e.message}}else{let t=Q.loadCases.find(t=>t.name===e);try{if(!t)throw Error(`This review ships no .comm for that load case.`);let e=Q.text.get(t.uri),r=e??await Aw(Q.baseUrl,t.uri);e||Q.text.set(t.uri,r),n={ok:!0,code:r}}catch(e){n={error:e.message}}}if(t!==Z.commRequest||e!==Z.codeTab)return;let{scrollTop:r}=J.commText;J.commText.dataset.state=n.ok?`ready`:`error`,J.commText.textContent=n.ok?n.code:Z.available?`${e}.comm could not be generated.\n\n${n.error??``}`:`${e}.comm is not part of this review.\n\n${n.error??``}`,J.commText.scrollTop=r}function zw(){let e=Z.project,t=!!e?.can_solve&&!Y.embed,n=Z.solving?`Solving…`:e?.solves?Nw().length>1?`Solve all`:`Solve`:`Build review`;for(let e of[J.solveButton,J.reviewEmptySolve])e.hidden=!t,e.disabled=Z.solving||Z.preparing,e.textContent=n;J.reviewEmpty.hidden=!(e&&Ew()===`review`&&!Z.hasReview),J.reviewEmptyText.textContent=Z.preparing?`Importing the review…`:Z.solving?`Solving model.py. The review opens here when Code_Aster finishes.`:e?.solves?`Not solved yet. Solve runs Code_Aster on model.py.`:`No review yet.`}var Bw=null;function Vw(){return Z.solveStartedAt?ae(Date.now()-Z.solveStartedAt):null}function Hw(e){e&&!Z.solveStartedAt&&(Z.solveStartedAt=Date.now()),e||(Z.solveStartedAt=null),e&&!Bw?Bw=setInterval(Ux,1e3):!e&&Bw&&(clearInterval(Bw),Bw=null)}async function Uw(){if(Z.solving||!Z.project?.can_solve)return;Z.solving=!0,$();let e=await fetch(`/api/solve`,{method:`POST`,headers:{"Content-Type":`application/json`},body:`{}`}).catch(e=>({ok:!1,status:0,json:async()=>({error:e.message})}));if(e.ok)return;let t=await e.json().catch(()=>({}));Z.solving=e.status===409,e.status===409?ew(`A solve is already running for this model.`):tw({message:t.error??`The studio refused to start a solve (HTTP ${e.status}).`},``),$()}async function Ww(e){if(Z.solving=e.type===`solve_started`,Z.preparing=!1,e.type===`solve_failed`||e.type===`review_failed`){let t=e.type===`solve_failed`?`Code_Aster did not finish. No results were produced.`:`The review could not be imported after the solve.`;tw({message:e.error},`${t} Open Technical details for the solver output.`)}if((e.type===`solve_finished`||e.type===`review_ready`)&&(Z.hasReview=!0,Z.reviewStale=!!e.review_stale,Ew()===`review`))if(n(Qb)===`review`)try{await Px(`review`,{preserve:!0})}catch(e){tw(e,`The finished review could not be loaded.`)}else await Kw(`review`);$()}async function Gw(e){!Z.available&&!Q.available||Ew()!==e&&(Z.available?await Kw(e):(e===`build`&&(Z.codeTab=null),Q.preview&&Xw(e)),X({type:`setStage`,stage:e}),e!==`build`&&!Z.available&&X({type:`resetLayerVisibility`}),$())}async function Kw(e){if(!Z.project)return;let t=e===`review`&&Z.hasReview?`review`:`build`;if(n(Qb)===t)return;Qb=t;let r=new URL(window.location.href);r.searchParams.set(`bundle`,t),window.history.replaceState({},``,r);try{await Px(t,{preserve:!0,reviewDefaultColor:t===`review`&&!tx&&!ex}),t===`review`&&(tx=!0)}catch(e){tw(e,`The ${t===`review`?`review`:`model`} could not be loaded.`)}}function qw(e){J.codeText.value=e,Z.ranCode=J.codeText.value,Z.revealLine=null,tT(),nT()}function Jw(){let e=!Z.available&&Dw()&&Q.preview?Q.preview.code:Z.ranCode;return l(J.codeText.value)!==l(e)}function Yw(){Cx?.cancel(),Cx=null,wx=``}function Xw(e){let t=e===`build`&&Q.preview?Q.preview.bundle:Zb;Y={...Pr(Yn(t)),...Je({review:t.review,embed:!1}),stage:e},rx=null,bx=[],yx=!1}async function Zw(){if(Cx){Yw(),$();return}let e=J.codeText.value;wx=`Starting…`,Z.error=null,J.codeProblem.hidden=!0;let t=mb(e,e=>{Cx===t&&(wx=e,Pw())});Cx=t,Pw();try{let n=await t.promise;if(Cx!==t)return;Q.preview={code:e,bundle:hb(n)},Dw()&&Xw(`build`)}catch(e){Cx===t&&e.name!==`AbortError`&&$w({error:e.message,line:e.line})}finally{Cx===t&&(Cx=null,wx=``,$(),!Z.error&&Dw()&&ux?.resetView())}}async function Qw(){if(!Z.available&&Q.available)return Zw();if(Z.running||!Z.available)return;Z.running=!0,J.codeRun.disabled=!0,J.codeState.textContent=`Running…`;let e=J.codeText.value;try{let t=await fetch(`/api/script`,{method:`POST`,headers:{"Content-Type":`application/json`},body:JSON.stringify({code:e})}),n=await t.json().catch(()=>({ok:!1,error:`Studio answered ${t.status}`}));if(!n.ok){$w(n);return}Z.ranCode=e,Z.error=null,Z.reviewStale=!!n.review_stale,J.codeProblem.hidden=!0,await Px(Qb,{preserve:!0}),Ax(J.buildIdentity,`Source`,await Dx(Z.ranCode)),await nx?.(),$();let r=Number(n.elements);J.codeState.textContent=Number.isFinite(r)?`Ran · ${r} element${r===1?``:`s`}`:`Ran`,ew(`Ready`)}catch(e){$w({error:e.message})}finally{Z.running=!1,J.codeRun.disabled=!1,nT()}}function $w({error:e,line:t}={}){let{message:n,detail:r}=kx(String(e??`model.py failed`),`model.py did not run.`);Z.error={message:n,line:Number.isInteger(t)&&t>0?t:null,detail:r},J.codeProblem.hidden=!1,J.codeProblem.replaceChildren();let i=document.createElement(`span`);if(i.className=`code-problem-summary`,i.textContent=Z.error.line?`Line ${Z.error.line}: ${n}`:n,J.codeProblem.append(i),r){let e=document.createElement(`details`);e.className=`code-problem-trace`;let t=document.createElement(`summary`);t.textContent=`Full output`;let n=document.createElement(`pre`);n.textContent=r,e.append(t,n),J.codeProblem.append(e)}J.codeState.textContent=`Failed · 3D shows the last good run`,Z.error.line&&oT(Z.error.line),iT()}async function eT(){if(!(!Z.available||Z.running||J.codeText.value!==Z.ranCode))try{let e=await fetch(`/api/script`,{cache:`no-store`}),t=e.ok?await e.json():null;if(typeof t?.code!=`string`||t.code===Z.ranCode)return;let{scrollTop:n}=J.codeText;qw(t.code),Ax(J.buildIdentity,`Source`,await Dx(Z.ranCode)),await nx?.(),J.codeText.scrollTop=n,Z.error=null,J.codeProblem.hidden=!0}catch{}}function tT(){let e=l(J.codeText.value);J.codeGutter.dataset.lines!==String(e)&&(J.codeGutter.dataset.lines=String(e),J.codeGutter.textContent=Array.from({length:e},(e,t)=>t+1).join(`
`))}function nT(){if(!Z.available){let e=document.createElement(`span`);e.textContent=Z.codeTab===null?`Update geometry executes Python in your browser. Review shows the published Code_Aster results; edits require a new solve. Use Exchange → Download model.py to save your edits.`:`Published solver input · read-only · not regenerated from draft edits`,J.codeFoot.replaceChildren(e);return}if(Z.codeTab!==null){let e=document.createElement(`span`);e.textContent=`Generated from model.py + study.py · read-only · solver input, not results`,J.codeFoot.replaceChildren(e);return}let e=J.codeText,t=document.createElement(`span`);t.textContent=e.value===Z.ranCode?`Saved to model.py`:`Edited · Ctrl+Enter runs and saves`;let n=document.createElement(`span`);n.textContent=`Ln ${p(e.value,e.selectionStart??0)}`;let r=[t,n];if(Z.available&&(Z.project?.load_cases??[]).length===0){let e=document.createElement(`span`);e.dataset.noStudyHint=``,e.textContent=`No study.py load cases — add LOAD_CASES to study.py for solver files and Solve`,r.push(e)}J.codeFoot.replaceChildren(...r)}function rT(){if(!Dw())return;let e=Y.objects.find(e=>e.id===rx),t=Number(e?.metadata?.source_line);Z.selectionLine=Number.isInteger(t)&&t>0&&!Jw()?t:null;let n=Number(e?.metadata?.source_call_line);Z.callLine=Z.selectionLine&&Number.isInteger(n)&&n>0?n:null,Z.revealedObjectId!==(e?.id??null)&&(Z.revealLine=null),Z.selectionLine&&Z.revealedObjectId!==e.id&&oT(Z.selectionLine),Z.revealedObjectId=e?.id??null,iT()}function iT(){aT(J.codeCallMark,Z.callLine),aT(J.codeRevealMark,Z.revealLine),aT(J.codeSelectionMark,Z.selectionLine),aT(J.codeErrorMark,Z.error?.line??null)}function aT(e,t){if(e.hidden=!t,!t)return;let n=getComputedStyle(J.codeText),r=parseFloat(n.paddingTop)+(t-1)*parseFloat(n.lineHeight)-J.codeText.scrollTop;e.style.transform=`translateY(${r}px)`}function oT(e,{focus:t=!1}={}){let n=J.codeText,r=parseFloat(getComputedStyle(n).lineHeight),i=(e-1)*r;if((i<n.scrollTop||i>n.scrollTop+n.clientHeight-2*r)&&(n.scrollTop=Math.max(0,i-n.clientHeight/3)),J.codeGutter.scrollTop=n.scrollTop,t){let t=f(n.value,e)+/^\s*/.exec(u(n.value,e))[0].length;n.focus({preventScroll:!0}),n.setSelectionRange(t,t),nT()}iT()}function sT(e){let t=document.createElement(`section`);t.className=`property-section script-link`;let n=document.createElement(`h3`);n.textContent=`Defined by`,t.append(n);let r=Number(e.metadata?.source_line);if(!Number.isInteger(r)||r<1)return t.append(iw(Z.available?`Run model.py to link this to the line that builds it.`:`This review records no source line for the selection.`)),t;if(Jw())return t.append(iw(`model.py:${r} when last run. Lines have moved since; run again to relink.`)),t;let i=u(J.codeText.value,r);t.append(cT(r,`model.py:${r}`));let a=Number(e.metadata?.source_call_line);if(Number.isInteger(a)&&a>0&&t.append(cT(a,`called from model.py:${a}`)),!Z.available&&!Q.available)return t;let o=s(i);if(o===null)return t;let l=document.createElement(`label`);l.className=`script-link-param`;let f=document.createElement(`span`);f.textContent=`Length`;let p=document.createElement(`input`);p.type=`number`,p.step=`any`,p.value=String(o),p.dataset.focusKey=`script-link-length`;let m=document.createElement(`span`);m.className=`script-link-unit`,m.textContent=`m`,p.addEventListener(`change`,()=>{let e=Number(p.value);if(p.value===``||!Number.isFinite(e)||e===o){p.value=String(o);return}if(Jw()||u(J.codeText.value,r)!==i){$();return}J.codeText.value=d(J.codeText.value,r,c(i,e)),J.codeText.dispatchEvent(new Event(`input`,{bubbles:!0})),Qw()}),l.append(f,p,m);let h=document.createElement(`p`);return h.className=`script-link-note`,h.textContent=Z.available?`Changing it rewrites this line and runs model.py.`:`Changing it runs a geometry preview in your browser. Engineering results require a new Code_Aster solve.`,t.append(l,h),t}function cT(e,t){let n=document.createElement(`button`);n.type=`button`,n.className=`script-link-reveal`,n.dataset.focusKey=`script-link:${e}`,n.title=`Show this line in model.py`;let r=document.createElement(`span`);r.className=`script-link-where`,r.textContent=t;let i=document.createElement(`code`);return i.textContent=u(J.codeText.value,e).trim(),n.append(r,i),n.addEventListener(`click`,()=>lT(e)),n}function lT(e){if(Jw()){$();return}Z.revealLine=e,Lw(null),oT(e,{focus:!0})}function uT(e){if(!Dw()||!Number.isInteger(e)||e<1||Jw())return null;let t=document.createElement(`button`);return t.type=`button`,t.className=`script-line-chip`,t.dataset.focusKey=`script-line-chip:${e}`,t.textContent=`:${e}`,t.title=`model.py:${e}  ${u(J.codeText.value,e).trim()}`,t.setAttribute(`aria-label`,`Show model.py line ${e}`),t.addEventListener(`click`,()=>lT(e)),t}for(let e of J.modeSwitch.querySelectorAll(`[data-mode]`))e.addEventListener(`click`,()=>void Gw(e.dataset.mode));for(let e of[J.solveButton,J.reviewEmptySolve])e.addEventListener(`click`,()=>void Uw());J.codeMeshToggle?.addEventListener(`click`,()=>{if(!Y)return;let e=!(kr(Y).find(e=>e.id===`analysis_mesh`)?.visible??!1);X({type:`setBodyVisibility`,bodyId:`analysis_mesh`,visible:e}),X({type:`setBodyOpacity`,bodyId:`geometry`,opacity:e?.35:1}),$()}),J.codeRun.addEventListener(`click`,()=>void Qw()),J.codeDownload.addEventListener(`click`,dT),J.codeReset.addEventListener(`click`,()=>{J.exchangeDialog.close(),Yw(),Sx.delete(Q.baseUrl),Q.preview=null,Z.error=null,J.codeProblem.hidden=!0,qw(Q.text.get(Q.scriptUri)),Xw(`build`),$()});function dT(){t(new Blob([J.codeText.value],{type:`text/x-python;charset=utf-8`}),`model.py`);let e=Sx.get(Q.baseUrl);e&&(e.downloaded=e.code)}window.addEventListener(`beforeunload`,e=>{[...Sx.values()].some(e=>e.code!==e.downloaded)&&(e.preventDefault(),e.returnValue=``)});var fT=300,pT=`tuba.codePaneWidthPx`;function mT(e){return Math.min(Math.max(Math.round(e),fT),Math.floor(window.innerWidth*.75))}function hT(){try{let e=Number.parseInt(window.localStorage.getItem(pT)??``,10);return Number.isFinite(e)?mT(e):null}catch{return null}}var gT=hT();function _T(){gT!=null&&document.body.dataset.mode===`build`?J.workspace.style.setProperty(`--controls-width`,`${gT}px`):J.workspace.style.removeProperty(`--controls-width`)}function vT(e){gT=mT(e),_T();try{window.localStorage.setItem(pT,String(gT))}catch{}}function yT(){gT=null,_T();try{window.localStorage.removeItem(pT)}catch{}}J.codeResize.addEventListener(`pointerdown`,e=>{if(e.button!==0)return;e.preventDefault(),J.codeResize.setPointerCapture(e.pointerId),J.codeResize.dataset.dragging=``;let t=e=>{vT(e.clientX-J.codePane.getBoundingClientRect().left)},n=()=>{delete J.codeResize.dataset.dragging,J.codeResize.removeEventListener(`pointermove`,t),J.codeResize.removeEventListener(`pointerup`,n),J.codeResize.removeEventListener(`pointercancel`,n)};J.codeResize.addEventListener(`pointermove`,t),J.codeResize.addEventListener(`pointerup`,n),J.codeResize.addEventListener(`pointercancel`,n)}),J.codeResize.addEventListener(`dblclick`,yT),J.codeText.addEventListener(`input`,()=>{if(Z.revealLine=null,!Z.available&&Q.available){let e=Q.baseUrl;Tx()?Sx.set(e,{code:J.codeText.value,downloaded:Sx.get(e)?.downloaded}):Sx.delete(e),Pw(),Ux(),Fw()}tT(),nT(),Jw()!==Z.linesMoved&&$(),rT()}),J.codeText.addEventListener(`scroll`,()=>{J.codeGutter.scrollTop=J.codeText.scrollTop,iT()});for(let e of[`click`,`keyup`])J.codeText.addEventListener(e,nT);J.codeText.addEventListener(`focus`,()=>{Z.tabLeavesEditor=!1}),J.codeText.addEventListener(`keydown`,e=>{let t=e.ctrlKey||e.metaKey;if(t&&(e.key===`Enter`||e.key.toLowerCase()===`s`)){e.preventDefault(),Z.available||e.key===`Enter`?Qw():Q.available&&dT();return}if(e.key===`Escape`){Z.tabLeavesEditor=!0;return}if(e.altKey&&e.key.toLowerCase()===`m`){e.preventDefault(),J.codeMeshToggle?.click();return}e.key!==`Tab`||e.shiftKey||t||e.altKey||Z.tabLeavesEditor||(e.preventDefault(),document.execCommand(`insertText`,!1,`    `)||(J.codeText.setRangeText(`    `,J.codeText.selectionStart,J.codeText.selectionEnd,`end`),J.codeText.dispatchEvent(new Event(`input`,{bubbles:!0}))))});var bT=[[`B`,`Build stage`,()=>void Gw(`build`),()=>!!J.modeSwitch&&!J.modeSwitch.hidden],[`R`,`Review stage`,()=>void Gw(`review`),()=>!!J.modeSwitch&&!J.modeSwitch.hidden],[`/`,`Find an object`,()=>{J.searchInput.focus(),J.searchInput.select()},()=>!J.searchInput.hidden],[`[`,`Previous issue`,()=>ST(-1),()=>!J.issueList.hidden],[`]`,`Next issue`,()=>ST(1),()=>!J.issueList.hidden],[`N`,`Previous finding`,()=>CT(-1),()=>Pt(Y).length>0],[`n`,`Next finding`,()=>CT(1),()=>Pt(Y).length>0],[`d`,`Plot the selected run`,()=>yS(),()=>!!_S()],[`F`,`Fit the whole scene`,()=>J.resetView.click(),()=>!J.resetView.hidden],[`?`,`Show this list`,()=>TT(!0),()=>!0]];function xT(e){return e instanceof HTMLElement?e.isContentEditable?!0:[`INPUT`,`TEXTAREA`,`SELECT`].includes(e.tagName):!1}window.addEventListener(`keydown`,e=>{if(e.altKey&&e.key.toLowerCase()===`m`&&Dw()){e.preventDefault(),J.codeMeshToggle?.click();return}if(!(e.ctrlKey||e.metaKey||e.altKey||xT(e.target))){if(e.key===`Escape`&&wT?.contains(document.activeElement)){TT(!1);return}if(e.key===`Escape`){TT(!1);return}for(let[t,,n,r]of bT)if(e.key===t){if(!r())return;e.preventDefault(),n();return}}});function ST(e){let t=[...J.issueList.querySelectorAll(`button`)];t.length!==0&&t[(t.findIndex(e=>e===document.activeElement)+e+t.length)%t.length].click()}function CT(e){let t=It(Y,e);t&&(rx=t.objectId,X({type:`focusFinding`,objectId:t.objectId}),$())}var wT=null;function TT(e){if(!(!e&&!wT)){if(e){wT||=ET(),document.body.append(wT),wT.querySelector(`button`)?.focus();return}wT?.remove()}}function ET(){let e=document.createElement(`div`);e.className=`shortcut-overlay`,e.setAttribute(`role`,`dialog`),e.setAttribute(`aria-modal`,`true`),e.setAttribute(`aria-label`,`Keyboard shortcuts`),e.dataset.shortcutOverlay=``;let t=document.createElement(`div`);t.className=`shortcut-panel`;let n=document.createElement(`h2`);n.textContent=`Keyboard`;let r=document.createElement(`button`);r.type=`button`,r.className=`shortcut-close`,r.setAttribute(`aria-label`,`Close shortcuts`),r.textContent=`Close`,r.addEventListener(`click`,()=>TT(!1));let i=document.createElement(`div`);i.className=`shortcut-head`,i.append(n,r);let a=document.createElement(`dl`);a.className=`shortcut-list`;for(let[e,t]of[...bT,[`Ctrl+Enter`,`Run model.py (Build)`],[`Ctrl+S`,`Download model.py`],[`Alt+M`,`Toggle the analysis mesh (Build)`]]){let n=document.createElement(`dt`),r=document.createElement(`kbd`);r.textContent=e,n.append(r);let i=document.createElement(`dd`);i.textContent=t,a.append(n,i)}return t.append(i,a),e.append(t),e.addEventListener(`click`,t=>{t.target===e&&TT(!1)}),e}Ex();export{kx as humanizeError};