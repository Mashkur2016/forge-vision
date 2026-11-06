"""
Browser-webcam live camera over WebSocket (no WebRTC / no TURN).

A self-contained HTML/JS panel: it captures the viewer's webcam, streams JPEG
frames to the FastAPI WebSocket endpoint (/api/v1/ws/live, reached on the same
origin via the Caddy proxy), and displays the annotated frames + AI feedback the
server streams back.

Frames are paced request/response (send the next frame only after the previous
result arrives), so it self-throttles to the server's CPU speed instead of
flooding — important on a free CPU host.

This is the deployed live-camera path. It replaced an earlier WebRTC attempt
(streamlit-webrtc / aiortc), which could not get a working TURN relay on the
target hosts; WebSocket works through a single public HTTP port (Hugging Face
Spaces).
"""
from __future__ import annotations

import streamlit as st
import streamlit.components.v1 as components

_HTML = r"""
<div style="font-family:system-ui,-apple-system,sans-serif;color:#1a1a1a">
  <video id="cam" autoplay muted playsinline style="display:none"></video>
  <img id="out" style="width:100%;height:__VH__px;object-fit:contain;background:#0f0f0f;border-radius:10px;display:block"/>
  <div style="display:flex;gap:8px;margin-top:10px;align-items:center;flex-wrap:wrap">
    <button id="startBtn" style="background:#FFCC00;border:none;font-weight:800;letter-spacing:.04em;padding:9px 18px;border-radius:8px;cursor:pointer">▶ START CAMERA</button>
    <button id="stopBtn" disabled style="background:#e5e7eb;border:none;font-weight:700;padding:9px 16px;border-radius:8px;cursor:pointer">■ STOP</button>
    <span id="status" style="font-size:13px;color:#6b7280">Idle — click Start and allow camera access</span>
    <span id="emo" style="margin-left:auto;font-size:13px;font-weight:600;color:#1a1a1a"></span>
  </div>
  <div id="fb" style="margin-top:12px"></div>
</div>
<script>
const TOKEN="__TOKEN__", SOP_ID="__SOP_ID__";
let ws=null, stream=null;
const canvas=document.createElement('canvas');
const out=document.getElementById('out'), statusEl=document.getElementById('status'), fb=document.getElementById('fb');
const startBtn=document.getElementById('startBtn'), stopBtn=document.getElementById('stopBtn'), cam=document.getElementById('cam');
const emo=document.getElementById('emo');
const EMO={focused:'🎯 Focused', neutral:'😐 Neutral', stressed:'😣 Stressed', fatigued:'😴 Fatigued'};
function showEmotion(e){ if(e && e.state) emo.textContent = EMO[e.state] || e.state; }
function setStatus(t){ statusEl.textContent=t; }
function loc(){ try{ return {h:window.parent.location.host, p:window.parent.location.protocol}; }catch(e){ return {h:location.host, p:location.protocol}; } }
function sendFrame(){
  if(!ws||ws.readyState!==1||!cam.videoWidth){ return; }
  const w=480, h=Math.round(cam.videoHeight*(480/cam.videoWidth));
  canvas.width=w; canvas.height=h;
  canvas.getContext('2d').drawImage(cam,0,0,w,h);
  try{ ws.send(canvas.toDataURL('image/jpeg',0.6)); }catch(e){}
}
function showFb(d){
  if(!d.deviation) return;
  const sev=(d.deviation.severity||'low');
  const color=sev==='high'?'#dc2626':(sev==='medium'?'#d97706':'#16a34a');
  fb.innerHTML='<div style="border-left:4px solid '+color+';padding:10px 14px;background:#fff;border:1px solid #eee;border-radius:8px">'
    +'<b style="color:'+color+'">'+sev.toUpperCase()+' — '+((d.deviation.what)||'')+'</b><br><span style="font-size:14px">'+((d.feedback)||'')+'</span></div>';
}
async function start(){
  try{ stream=await navigator.mediaDevices.getUserMedia({video:{width:{ideal:640}},audio:false}); }
  catch(e){ setStatus('Camera blocked: '+e.message); return; }
  cam.srcObject=stream; await cam.play();
  const l=loc(); const proto=(l.p==='https:')?'wss':'ws';
  setStatus('Connecting…');
  ws=new WebSocket(proto+'://'+l.h+'/api/v1/ws/live?token='+encodeURIComponent(TOKEN)+'&sop_id='+encodeURIComponent(SOP_ID));
  ws.onopen=()=>{ setStatus('● LIVE'); startBtn.disabled=true; stopBtn.disabled=false; sendFrame(); };
  ws.onmessage=(e)=>{ let d; try{ d=JSON.parse(e.data); }catch(_){ return; } if(d.error){ setStatus('Error: '+d.error); return; } if(d.frame) out.src=d.frame; if(d.emotion) showEmotion(d.emotion); showFb(d); sendFrame(); };
  ws.onclose=()=>{ setStatus('Disconnected'); startBtn.disabled=false; stopBtn.disabled=true; };
  ws.onerror=()=>{ setStatus('Connection error'); };
}
function stop(){ if(ws){ try{ws.close();}catch(e){} ws=null; } if(stream){ stream.getTracks().forEach(t=>t.stop()); stream=null; } setStatus('Stopped'); startBtn.disabled=false; stopBtn.disabled=true; }
startBtn.onclick=start; stopBtn.onclick=stop;
window.addEventListener('beforeunload', stop);
</script>
"""


def ws_camera_panel(token: str, sop_id: str, height: int = 560) -> None:
    """Render the WebSocket live-camera panel (video + inline AI feedback)."""
    html = (
        _HTML
        .replace("__TOKEN__", token or "")
        .replace("__SOP_ID__", sop_id or "")
        .replace("__VH__", str(max(240, height - 150)))
    )
    components.html(html, height=height)
