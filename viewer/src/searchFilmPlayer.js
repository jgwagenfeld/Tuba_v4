// A player for the encoded movie, with layout chapters rather than a result
// field menu. It uses the held-frame times from the capture manifest.
import { hydraulicSolverLabel } from './searchReplay.js';

export function filmPlayer(plan) {
  const escape = value => String(value).replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;');
  const chapters = plan.keyframes.map((frame, index) => ({ time: frame.start_frame / plan.fps,
    label: frame.phase === 'selection' ? 'Final choice' : `${frame.candidate_id}${frame.outcome === 'interrupted' ? ' · interrupted'
      : plan.keyframes.slice(0, index).some(f => f.candidate_id === frame.candidate_id && f.evaluation_id !== frame.evaluation_id) ? ' · retry' : ''}`,
    description: frame.caption.split('\n\n').slice(0, 2).join(' · ') }));
  const fluid = plan.keyframes.some(frame => frame.fluid_results);
  const solvers = [...new Set(plan.keyframes.filter(frame => frame.fluid_results).map(frame =>
    hydraulicSolverLabel(frame.hydraulic_basis ?? frame.check?.basis ?? frame.checks?.find(c => hydraulicSolverLabel(c.basis))?.basis) ?? 'hydraulic solver'))].join(' and ');
  const duration = `${Math.floor(plan.duration_seconds / 60)}:${String(Math.round(plan.duration_seconds % 60)).padStart(2, '0')}`;
  return `<!doctype html>
<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Piping search — each tested layout</title>
<style>body{margin:16px;background:#f8fafc;color:#17233a;font:17px system-ui}h1{font-size:25px;margin:0 0 10px}p{max-width:1400px;line-height:1.5}video{display:block;width:100%;max-width:1600px;background:#f8fafc}nav{display:flex;flex-wrap:wrap;gap:8px;margin:12px 0}button{font:inherit;padding:9px 13px;border:1px solid #9aa9be;border-radius:5px;background:white;cursor:pointer}button[aria-current=true]{background:#17233a;color:white}.active{font-weight:600}</style>
<h1>Piping search — each tested layout</h1>
<p>Follow the different piping layouts in the order they were tested. Each iteration shows what changed, its recorded outcome and the reasons on the drawing. <strong>Red rings mark failed collision, clearance, hydraulic or load checks.</strong> Solved layouts also show coloured pipe stress, blue support forces and orange support moments together.</p>
<nav aria-label="Playback"><button id="play-search">Play all iterations (${duration})</button></nav>
<p id="current-view" class="active">${escape(chapters[0]?.description ?? 'Recorded search')}</p>
<video controls preload="metadata" poster="${escape(plan.keyframes[0]?.png ?? '')}" src="film.webm"></video>
<nav aria-label="Piping iterations">${chapters.map((c, i) => `<button data-chapter="${i}">${escape(c.label)}</button>`).join('')}</nav>
<p>${fluid ? `Hydraulic rejections show retained ${escape(solvers)} fluid fields; Code_Aster loads and stress remain unavailable until evaluated.` : 'Layouts rejected before a solve show their geometry findings; their loads and stress are unavailable.'} Interrupted attempts stay separate from successful retries. Feasible layouts stay labelled feasible until the final comparison.</p>
<p>${fluid ? `Fluid fields come from retained ${escape(solvers)} evaluations (m/s, absolute Pa and K). Structural fields come from retained Code_Aster evaluations.` : 'Results come from retained Code_Aster evaluations.'} Pipe colours show element maximum FE von Mises stress in MPa; blue and orange glyphs show reactions on the model in N and N m. The pipe is the reference layout; collision markers use the recorded cold or physical operating-check locations. These checks do not establish piping-code compliance.</p>
<script>
const chapters=${JSON.stringify(chapters).replaceAll('<', '\\u003c')};
const video=document.querySelector('video'), status=document.querySelector('#current-view');
function seek(time,play=false){video.pause();const apply=()=>{video.currentTime=time;if(play)video.play().catch(console.error);};if(video.readyState>=1)apply();else video.addEventListener('loadedmetadata',apply,{once:true});}
document.querySelector('#play-search').addEventListener('click',()=>seek(0,true));
for(const button of document.querySelectorAll('[data-chapter]'))button.addEventListener('click',()=>seek(chapters[Number(button.dataset.chapter)].time));
video.addEventListener('timeupdate',()=>{let index=0;for(let i=0;i<chapters.length;i++)if(chapters[i].time<=video.currentTime+.02)index=i;status.textContent=chapters[index].description;for(const button of document.querySelectorAll('[data-chapter]'))button.setAttribute('aria-current',String(Number(button.dataset.chapter)===index));});
</script></html>`;
}
