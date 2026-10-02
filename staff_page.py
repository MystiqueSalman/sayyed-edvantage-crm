"""Staff & Faculty management page for the Sayyed EdVantage CRM dashboard.

Lists pending admin/faculty signup requests for Salman's approval and the
active staff roster. Served at /staff (auth handled by the main server).
"""
from __future__ import annotations

import html as _html


def _esc(value) -> str:
    return _html.escape(str(value or ""), quote=True)


def staff_page() -> str:
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Staff &amp; Faculty — Sayyed EdVantage CRM</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Segoe UI',Arial,sans-serif;background:#f4f6fb;color:#1e2a3a}
header{background:linear-gradient(120deg,#0a1030,#1a1440);color:#fff;padding:22px 34px}
header h1{font-size:22px}
header h1 span{color:#e8b93c}
header p{font-size:13px;opacity:.75;margin-top:4px}
nav{background:#fff;border-bottom:1px solid #dfe5ee;padding:10px 34px;display:flex;gap:8px;flex-wrap:wrap}
.nav-link{padding:9px 16px;border-radius:8px;text-decoration:none;color:#33415c;font-weight:600;font-size:14px}
.nav-link.active{background:#0a1030;color:#e8b93c}
main{padding:26px 34px;max-width:1100px}
h2{font-size:18px;margin:6px 0 14px}
.card{background:#fff;border:1px solid #e3e8f2;border-radius:12px;padding:20px;margin-bottom:24px;box-shadow:0 2px 8px rgba(10,16,48,.05)}
table{width:100%;border-collapse:collapse;font-size:14px}
th{text-align:left;padding:10px 12px;background:#f1f4fa;color:#5a6c8d;font-size:12px;text-transform:uppercase;letter-spacing:.6px}
td{padding:12px;border-top:1px solid #eef1f7;vertical-align:middle}
.pill{display:inline-block;font-size:12px;font-weight:700;padding:4px 12px;border-radius:20px}
.pill.pending{background:#fff4d6;color:#8a6d1c}
.pill.approved{background:#dff7e6;color:#1c7a3d}
.pill.rejected{background:#ffe3e3;color:#b03a3a}
.pill.admin{background:#e8e4ff;color:#4a3aff}
.pill.faculty{background:#dff1ff;color:#1769aa}
.btn{border:none;border-radius:8px;padding:8px 16px;font-size:13px;font-weight:700;cursor:pointer;margin-right:8px}
.btn.approve{background:#1c7a3d;color:#fff}
.btn.reject{background:#fff;border:1px solid #e0a3a3;color:#b03a3a}
.btn:disabled{opacity:.5;cursor:default}
.muted{color:#8a94a8;font-size:13px}
.msg{font-size:13px;margin-top:10px;min-height:18px}
.msg.ok{color:#1c7a3d}.msg.err{color:#b03a3a}
@media(max-width:700px){main{padding:16px}td,th{padding:8px}}
</style>
</head>
<body>
<header><h1>Sayyed <span>EdVantage</span></h1><p>Admissions CRM &amp; Counselling Manager</p></header>
<nav>
<a class="nav-link" href="/">Lead Manager</a>
<a class="nav-link" href="/counselling">Counselling Manager</a>
<a class="nav-link" href="/follow-ups">Follow-up Manager</a>
<a class="nav-link active" href="/staff">Staff &amp; Faculty</a>
</nav>
<main>
<div class="card">
<h2>⏳ Pending approvals</h2>
<div id="pendingBox"><p class="muted">Loading…</p></div>
<div class="msg" id="pendingMsg"></div>
</div>
<div class="card">
<h2>👥 Staff &amp; faculty</h2>
<div id="staffBox"><p class="muted">Loading…</p></div>
<div class="msg" id="staffMsg"></div>
</div>
</main>
<script>
function staffToken(){
  const m=document.cookie.match(/(?:^|;\\s*)se_staff=([^;]+)/);
  return m?decodeURIComponent(m[1]):"";
}
async function api(path,body){
  body=body||{};const t=staffToken();if(t)body.session_token=t;
  const r=await fetch(path,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
  return r.json();
}
function esc(s){return String(s==null?"":s).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));}
async function loadPending(){
  const box=document.getElementById("pendingBox");
  try{
    const r=await api("/api/public/staff-pending",{});
    if(!r.ok){box.innerHTML='<p class="muted">Could not load.</p>';return;}
    if(!r.pending.length){box.innerHTML='<p class="muted">No pending requests. New admin/faculty signups will appear here.</p>';return;}
    let h='<table><tr><th>Name</th><th>Role</th><th>Username</th><th>Contact</th><th>Requested</th><th></th></tr>';
    r.pending.forEach(p=>{
      h+='<tr><td><b>'+esc(p.full_name)+'</b><br><span class="muted">'+esc(p.staff_id)+'</span></td>'
        +'<td><span class="pill '+p.role+'">'+p.role+'</span></td>'
        +'<td>'+esc(p.username)+'</td>'
        +'<td><span class="muted">'+esc(p.email)+'<br>'+esc(p.phone)+'</span></td>'
        +'<td><span class="muted">'+esc((p.created_at||"").slice(0,10))+'</span></td>'
        +'<td><button class="btn approve" data-u="'+esc(p.username)+'">Approve</button>'
        +'<button class="btn reject" data-u="'+esc(p.username)+'">Reject</button></td></tr>';
    });
    box.innerHTML=h+'</table>';
    box.querySelectorAll(".btn.approve").forEach(b=>b.addEventListener("click",()=>decide(b.dataset.u,"approve",b)));
    box.querySelectorAll(".btn.reject").forEach(b=>b.addEventListener("click",()=>decide(b.dataset.u,"reject",b)));
  }catch(e){box.innerHTML='<p class="muted">Could not load.</p>';}
}
async function decide(username,action,btn){
  const msg=document.getElementById("pendingMsg");msg.className="msg";msg.textContent="";
  btn.disabled=true;
  try{
    const r=await api("/api/public/staff-"+action,{username:username});
    if(r.ok){msg.textContent=username+" "+(action==="approve"?"approved.":"rejected.");msg.classList.add("ok");loadPending();loadStaff();}
    else{msg.textContent="Failed.";msg.classList.add("err");btn.disabled=false;}
  }catch(e){msg.textContent="Server unreachable.";msg.classList.add("err");btn.disabled=false;}
}
async function loadStaff(){
  const box=document.getElementById("staffBox");
  try{
    const r=await api("/api/public/staff-list",{});
    if(!r.ok){box.innerHTML='<p class="muted">Could not load.</p>';return;}
    if(!r.staff.length){box.innerHTML='<p class="muted">No staff accounts yet.</p>';return;}
    let h='<table><tr><th>Name</th><th>Role</th><th>Status</th><th>Username</th><th>Since</th><th></th></tr>';
    r.staff.forEach(p=>{
      h+='<tr><td><b>'+esc(p.full_name)+'</b><br><span class="muted">'+esc(p.staff_id)+'</span></td>'
        +'<td><span class="pill '+p.role+'">'+p.role+'</span></td>'
        +'<td><span class="pill '+p.status+'">'+p.status+'</span></td>'
        +'<td>'+esc(p.username)+'</td>'
        +'<td><span class="muted">'+esc((p.created_at||"").slice(0,10))+'</span></td>'
        +'<td>'+(p.status==="approved"
            ?'<button class="btn reject" data-u="'+esc(p.username)+'">Disable</button>'
            :p.status!=="pending"?'<button class="btn approve" data-u="'+esc(p.username)+'">Re-approve</button>':"")
        +'</td></tr>';
    });
    box.innerHTML=h+'</table>';
    box.querySelectorAll(".btn").forEach(b=>b.addEventListener("click",async()=>{
      const msg=document.getElementById("staffMsg");msg.className="msg";msg.textContent="";
      b.disabled=true;
      const action=b.classList.contains("approve")?"approve":"reject";
      try{
        const r=await api("/api/public/staff-"+action,{username:b.dataset.u});
        if(r.ok){msg.textContent="Updated.";msg.classList.add("ok");loadPending();loadStaff();}
        else{msg.textContent="Failed.";msg.classList.add("err");b.disabled=false;}
      }catch(e){msg.textContent="Server unreachable.";msg.classList.add("err");b.disabled=false;}
    }));
  }catch(e){box.innerHTML='<p class="muted">Could not load.</p>';}
}
loadPending();loadStaff();
</script>
</body>
</html>"""
