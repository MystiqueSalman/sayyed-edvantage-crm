from __future__ import annotations
import html, json
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse, urlencode

ROOT=Path(__file__).resolve().parent
DATA=ROOT/'data'; LEADS=DATA/'leads.json'; HOST='127.0.0.1'; PORT=8000
BRAND_LOGO_SVG="""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 520 120">
<defs>
<linearGradient id="gold" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#F7D774"/><stop offset="1" stop-color="#A87518"/></linearGradient>
<linearGradient id="blue" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#56C2FF"/><stop offset="1" stop-color="#1769AA"/></linearGradient>
</defs>
<g transform="translate(8 8)">
<path d="M40 25 L92 7 L144 25 L92 42 Z" fill="#14213D"/><path d="M144 25v21" stroke="#D7A93B" stroke-width="4"/><circle cx="144" cy="50" r="4" fill="#D7A93B"/>
<text x="35" y="82" font-family="Arial" font-size="68" font-weight="800" fill="url(#gold)">S</text>
<text x="78" y="82" font-family="Arial" font-size="68" font-weight="800" fill="url(#blue)">E</text>
<path d="M37 91 Q92 64 147 91" fill="none" stroke="#56C2FF" stroke-width="5"/>
<path d="M47 94 Q92 76 137 94" fill="none" stroke="#D7A93B" stroke-width="3"/>
</g>
<text x="180" y="54" font-family="Arial" font-size="31" font-weight="800" fill="#D7A93B">SAYYED</text>
<text x="180" y="88" font-family="Arial" font-size="30" font-weight="700" fill="#56C2FF">EdVantage</text>
<text x="180" y="108" font-family="Arial" font-size="10" letter-spacing="2" fill="#FFFFFF">EMPOWERING STUDENTS FOR SUCCESS</text>
</svg>"""

STATUSES=['New','Contacted','Counselling','Interested','Application','Payment Pending','Enrolled','Lost']
PAYMENT_STATUSES=['Not Started','Quotation Sent','Payment Pending','Partially Paid','Paid','Refunded']
SOURCES=['AI Agent','Website','Google Ads','Instagram','Facebook','YouTube','WhatsApp','Referral','School/College','Other']
COUNSELLING_MODES=['Phone','WhatsApp','Video Call','In Person','Email','Other']
COUNSELLING_OUTCOMES=['Pending','Interested','Call Back','Application','Payment Pending','Enrolled','Not Interested','Lost']
PAYMENT_MODES=['Cash','UPI','Bank Transfer','Card','Online','Other']
FOLLOWUP_OUTCOMES=['Contacted','No Answer','Call Back','Interested','Not Interested','Application','Payment Pending','Enrolled','Lost']
STATUS_MAP={'Contacted':'Contacted','No Answer':'Contacted','Call Back':'Contacted','Interested':'Interested','Not Interested':'Lost','Application':'Application','Payment Pending':'Payment Pending','Enrolled':'Enrolled','Lost':'Lost'}

def now(): return datetime.now().isoformat(timespec='seconds')
def today(): return date.today().isoformat()
def esc(v): return html.escape('' if v is None else str(v))
def dec(v):
    try: return Decimal(str(v or '0').replace(',','').strip())
    except (InvalidOperation,ValueError,TypeError): return Decimal('0')
def vdate(v):
    if not str(v or '').strip(): return True
    try: datetime.strptime(str(v),'%Y-%m-%d'); return True
    except ValueError: return False
def vtime(v):
    if not str(v or '').strip(): return True
    try: datetime.strptime(str(v),'%H:%M'); return True
    except ValueError: return False

def ensure():
    DATA.mkdir(parents=True,exist_ok=True)
    if not LEADS.exists(): LEADS.write_text('{}',encoding='utf-8')
    else:
        try:
            if not isinstance(json.loads(LEADS.read_text(encoding='utf-8')),dict): raise ValueError
        except Exception:
            backup=LEADS.with_suffix('.invalid.json')
            try: LEADS.replace(backup)
            except OSError: pass
            LEADS.write_text('{}',encoding='utf-8')

def load():
    ensure()
    try:
        x=json.loads(LEADS.read_text(encoding='utf-8')); return x if isinstance(x,dict) else {}
    except Exception: return {}
def save(x):
    ensure(); tmp=LEADS.with_suffix('.tmp'); tmp.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8'); tmp.replace(LEADS)
def all_leads(): return [x for x in load().values() if isinstance(x,dict)]
def lead(lid): return load().get(lid)
def hist(l,key):
    x=l.get(key,[])
    if not isinstance(x,list): x=[]; l[key]=x
    return x

def recalc(l):
    final=max(Decimal('0'),dec(l.get('final_fee'))); paid=max(Decimal('0'),dec(l.get('total_paid')))
    l['total_paid']=float(paid); l['balance_amount']=float(max(Decimal('0'),final-paid))
    if final<=0: l['payment_status']=l.get('payment_status') or 'Not Started'
    elif paid<=0: l['payment_status']='Not Started'
    elif paid<final: l['payment_status']='Partially Paid'
    else: l['payment_status']='Paid'

def update(lid,**u):
    db=load(); l=db.get(lid)
    if not isinstance(l,dict): return None
    allowed={'name','phone','email','country','preferred_language','course_interest','education','message','source','status','payment_status','follow_up_date','follow_up_time','assigned_counsellor','follow_up_notes','international_student','student_type','currency'}
    for k,v in u.items():
        if k in allowed: l[k]=v
    l['updated_at']=now(); save(db); return l

def add_counselling(lid,counsellor,cd,ct,mode,outcome,notes,nd,nt):
    db=load(); l=db.get(lid)
    if not isinstance(l,dict): return None
    if mode not in COUNSELLING_MODES: mode='Phone'
    if outcome not in COUNSELLING_OUTCOMES: outcome='Pending'
    t=now(); h=hist(l,'counselling_history')
    s={'session_id':f'CS-{len(h)+1:05d}','counsellor':counsellor.strip(),'counselling_date':cd.strip(),'counselling_time':ct.strip(),'mode':mode,'outcome':outcome,'notes':notes.strip(),'next_follow_up_date':nd.strip(),'next_follow_up_time':nt.strip(),'created_at':t,'updated_at':t}
    h.append(s); l['counselling_history']=h
    if s['counsellor']: l['assigned_counsellor']=s['counsellor']
    l['last_contacted_at']=t; l['follow_up_date']=s['next_follow_up_date']; l['follow_up_time']=s['next_follow_up_time']
    if s['notes']: l['follow_up_notes']=s['notes']
    if outcome in {'Interested','Application','Payment Pending','Enrolled','Not Interested','Lost'}: l['status']={'Not Interested':'Lost'}.get(outcome,outcome)
    l['updated_at']=t; save(db); return s

def add_followup(lid,outcome,notes,nd,nt,counsellor):
    db=load(); l=db.get(lid)
    if not isinstance(l,dict): return None
    if outcome not in FOLLOWUP_OUTCOMES: outcome='Contacted'
    if outcome in {'Enrolled','Lost','Not Interested'}: nd=nt=''
    t=now(); h=hist(l,'follow_up_history'); new=STATUS_MAP.get(outcome,l.get('status','New'))
    a={'action_id':f'FU-{len(h)+1:05d}','action_at':t,'counsellor':counsellor.strip(),'outcome':outcome,'notes':notes.strip(),'previous_follow_up_date':str(l.get('follow_up_date','')),'previous_follow_up_time':str(l.get('follow_up_time','')),'next_follow_up_date':nd.strip(),'next_follow_up_time':nt.strip(),'status_after':new}
    h.append(a); l['follow_up_history']=h; l['last_contacted_at']=t; l['status']=new; l['follow_up_date']=a['next_follow_up_date']; l['follow_up_time']=a['next_follow_up_time']
    if counsellor.strip(): l['assigned_counsellor']=counsellor.strip()
    if notes.strip(): l['follow_up_notes']=notes.strip()
    l['updated_at']=t; save(db); return a

def set_fee(lid,base,discount,currency,converted):
    db=load(); l=db.get(lid)
    if not isinstance(l,dict): return None
    b=max(Decimal('0'),dec(base)); d=max(Decimal('0'),dec(discount))
    if d>b: return None
    l.update(base_fee=float(b),discount=float(d),final_fee=float(b-d),currency=(currency or 'INR').strip() or 'INR',converted_amount=float(max(Decimal('0'),dec(converted))))
    recalc(l); l['updated_at']=now(); save(db); return l

def pay(lid,amount,mode,ref,pdate,notes):
    db=load(); l=db.get(lid)
    if not isinstance(l,dict): return None
    a=dec(amount)
    if a<=0: return None
    final=dec(l.get('final_fee')); paid=dec(l.get('total_paid'))
    if final>0 and paid+a>final: return None
    if mode not in PAYMENT_MODES: mode='Other'
    p={'payment_id':f'PAY-{len(hist(l,"payment_history"))+1:05d}','amount':float(a),'payment_mode':mode,'transaction_id':ref.strip(),'payment_date':(pdate or now()[:10]).strip(),'notes':notes.strip(),'recorded_at':now()}
    hist(l,'payment_history').append(p); l['total_paid']=float(paid+a); l['payment_mode']=mode; l['transaction_id']=p['transaction_id']; l['payment_date']=p['payment_date']; recalc(l); l['updated_at']=now(); save(db); return p

def opts(values,selected=''):
    return ''.join(f'<option value="{esc(v)}" {"selected" if str(v).lower()==str(selected or "").lower() else ""}>{esc(v)}</option>' for v in values)

def nav(active):
    return ''.join(f'<a class="nav {"active" if k==active else ""}" href="{u}">{n}</a>' for k,u,n in [('dashboard','/','Lead Manager'),('counselling','/counselling','Counselling Manager'),('followups','/follow-ups','Follow-up Manager')])

"""
/* ============================================================
   SAYYED EDVANTAGE - FINAL PROFESSIONAL BRAND SYSTEM
   Visual-only override. CRM logic is untouched.
   ============================================================ */

:root{
  --sev-navy:#06152f;
  --sev-navy-2:#0a1d3d;
  --sev-blue:#1769aa;
  --sev-bright-blue:#1677b8;
  --sev-gold:#f5c542;
  --sev-white:#ffffff;
}

/* Main brand header */
header.brand-header{
  position:relative !important;
  width:100% !important;
  min-height:248px !important;
  padding:0 !important;
  overflow:hidden !important;
  color:#fff !important;
  background:
    radial-gradient(circle at 82% 45%,
      rgba(37,119,188,.30) 0%,
      rgba(19,70,121,.16) 32%,
      transparent 61%),
    linear-gradient(105deg,
      #06152f 0%,
      #0a1d3d 42%,
      #123d69 73%,
      #1769a1 100%) !important;
  border-bottom:2px solid rgba(72,168,235,.72) !important;
  box-shadow:none !important;
}

/* Premium background rings */
header.brand-header:after{
  content:"" !important;
  position:absolute !important;
  width:520px !important;
  height:520px !important;
  right:70px !important;
  top:-138px !important;
  border-radius:50% !important;
  border:1px solid rgba(117,190,239,.12) !important;
  box-shadow:
    0 0 0 85px rgba(117,190,239,.035),
    0 0 0 170px rgba(117,190,239,.022) !important;
  pointer-events:none !important;
  background:transparent !important;
}

/* Header content */
header.brand-header .brand-inner{
  position:relative !important;
  z-index:2 !important;
  width:100% !important;
  max-width:1650px !important;
  min-height:248px !important;
  margin:0 auto !important;
  padding:0 42px !important;
  display:flex !important;
  align-items:center !important;
  gap:36px !important;
  box-sizing:border-box !important;
}

/* Large transparent logo zone - no crop/card */
header.brand-header .brand-mark{
  position:relative !important;
  flex:0 0 520px !important;
  width:520px !important;
  min-width:520px !important;
  height:210px !important;
  display:flex !important;
  align-items:center !important;
  justify-content:center !important;
  background:transparent !important;
  border:0 !important;
  box-shadow:none !important;
  overflow:visible !important;
}

/* Preserve the existing official logo */
header.brand-header .brand-mark img,
header.brand-header .brand-logo{
  display:block !important;
  width:100% !important;
  max-width:520px !important;
  height:100% !important;
  max-height:210px !important;
  object-fit:contain !important;
  object-position:center !important;
  background:transparent !important;
  border:0 !important;
  outline:0 !important;
  box-shadow:none !important;
}

/* Divider */
header.brand-header .brand-copy{
  position:relative !important;
  flex:1 1 auto !important;
  min-width:0 !important;
  padding:12px 0 12px 38px !important;
  border-left:1px solid rgba(255,255,255,.24) !important;
  background:transparent !important;
}

/* Gold label */
header.brand-header .brand-kicker{
  margin:0 0 14px !important;
  font-family:"Segoe UI",Arial,sans-serif !important;
  font-size:15px !important;
  line-height:1.2 !important;
  font-weight:800 !important;
  letter-spacing:4px !important;
  color:var(--sev-gold) !important;
  text-transform:uppercase !important;
}

/* Command title */
header.brand-header .brand-copy h1,
header.brand-header .brand-title h1{
  margin:0 !important;
  color:#fff !important;
  font-family:"Segoe UI",Arial,sans-serif !important;
  font-size:clamp(34px,3vw,50px) !important;
  line-height:1.12 !important;
  font-weight:800 !important;
  letter-spacing:-1px !important;
  text-shadow:0 2px 8px rgba(0,0,0,.22) !important;
}

/* Subtitle */
header.brand-header .brand-copy p,
header.brand-header .brand-title p{
  margin:14px 0 0 !important;
  color:rgba(255,255,255,.82) !important;
  font-family:"Segoe UI",Arial,sans-serif !important;
  font-size:clamp(16px,1.35vw,20px) !important;
  line-height:1.55 !important;
}

/* Responsive */
@media(max-width:1200px){
  header.brand-header .brand-inner{
    padding:0 28px !important;
    gap:24px !important;
  }
  header.brand-header .brand-mark{
    flex-basis:430px !important;
    width:430px !important;
    min-width:430px !important;
    height:185px !important;
  }
  header.brand-header .brand-mark img,
  header.brand-header .brand-logo{
    max-width:430px !important;
    max-height:185px !important;
  }
  header.brand-header .brand-copy{
    padding-left:28px !important;
  }
  header.brand-header .brand-kicker{
    font-size:13px !important;
    letter-spacing:3px !important;
  }
}

@media(max-width:850px){
  header.brand-header{
    min-height:auto !important;
  }
  header.brand-header .brand-inner{
    min-height:auto !important;
    padding:22px 24px 26px !important;
    flex-direction:column !important;
    align-items:stretch !important;
    gap:18px !important;
  }
  header.brand-header .brand-mark{
    width:100% !important;
    min-width:0 !important;
    flex-basis:auto !important;
    height:165px !important;
  }
  header.brand-header .brand-mark img,
  header.brand-header .brand-logo{
    width:min(100%,620px) !important;
    max-width:620px !important;
    height:165px !important;
    max-height:165px !important;
    margin:auto !important;
  }
  header.brand-header .brand-copy{
    padding:20px 0 0 !important;
    border-left:0 !important;
    border-top:1px solid rgba(255,255,255,.22) !important;
  }
  header.brand-header .brand-copy h1,
  header.brand-header .brand-title h1{
    font-size:32px !important;
  }
}

@media(max-width:600px){
  header.brand-header .brand-inner{
    padding:16px 16px 22px !important;
  }
  header.brand-header .brand-mark{
    height:135px !important;
  }
  header.brand-header .brand-mark img,
  header.brand-header .brand-logo{
    height:135px !important;
  }
  header.brand-header .brand-kicker{
    font-size:11px !important;
    letter-spacing:2.2px !important;
  }
  header.brand-header .brand-copy h1,
  header.brand-header .brand-title h1{
    font-size:27px !important;
  }
  header.brand-header .brand-copy p,
  header.brand-header .brand-title p{
    font-size:15px !important;
  }
}

"""


def page(title,active,body):
    page_titles={
        'dashboard':('Admissions Command Center','Manage leads, counselling, follow-ups, payments and admissions.'),
        'counselling':('Counselling Command Center','Track every counselling conversation, outcome and next action.'),
        'followups':('Follow-up Command Center','Never miss the next student contact or admission action.'),
    }
    heading,subtitle=page_titles.get(active,(title,'Sayyed EdVantage Admissions CRM'))
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)} — Sayyed EdVantage</title><style>{CSS}</style></head><body>
<header class="brand-header"><div class="brand-inner">
<img class="brand-logo" src="/brand-logo.svg" alt="Sayyed EdVantage">
<div class="brand-title"><div class="brand-kicker">ADMISSIONS • CRM • AI SALES</div>
<h1>{esc(heading)}</h1><p>{esc(subtitle)}</p></div></div></header>
<nav>{nav(active)}</nav><main>{body}</main></body></html>"""

def filt(leads,p):
    q=p.get('q',[''])[0].strip().lower(); out=[]
    for l in leads:
        checks={'status':'','country':'','source':'','payment_status':'','assigned_counsellor':''}
        for k in checks:
            v=p.get('counsellor',[''])[0] if k=='assigned_counsellor' else p.get(k,[''])[0]
            if v and str(l.get(k,'')).lower()!=v.lower(): break
        else:
            if p.get('course',[''])[0] and p['course'][0].lower() not in str(l.get('course_interest','')).lower(): continue
            if p.get('name',[''])[0] and p['name'][0].lower() not in str(l.get('name','')).lower(): continue
            if p.get('lead_id',[''])[0] and p['lead_id'][0].lower() not in str(l.get('lead_id','')).lower(): continue
            if p.get('phone',[''])[0] and p['phone'][0].lower() not in str(l.get('phone','')).lower(): continue
            if p.get('email',[''])[0] and p['email'][0].lower() not in str(l.get('email','')).lower(): continue
            if p.get('created_date',[''])[0] and not str(l.get('created_at','')).startswith(p['created_date'][0]): continue
            if p.get('follow_up_date',[''])[0] and str(l.get('follow_up_date',''))!=p['follow_up_date'][0]: continue
            if q and q not in ' '.join(str(l.get(k,'')) for k in ('lead_id','name','phone','email','country','course_interest','education','source','assigned_counsellor','follow_up_notes')).lower(): continue
            out.append(l)
    return out

def dashboard(p):
    leads=all_leads(); fs=filt(leads,p); sc={s:0 for s in STATUSES}; pc={s:0 for s in PAYMENT_STATUSES}; src={}; fee=paid=bal=Decimal('0'); due=over=up=0
    for l in leads:
        s=str(l.get('status') or 'New'); sc[s]=sc.get(s,0)+1; ps=str(l.get('payment_status') or 'Not Started'); pc[ps]=pc.get(ps,0)+1; z=str(l.get('source') or 'Other'); src[z]=src.get(z,0)+1; fee+=dec(l.get('final_fee')); paid+=dec(l.get('total_paid')); bal+=dec(l.get('balance_amount')); fd=str(l.get('follow_up_date','')); due+=fd==today(); over+=bool(fd and fd<today()); up+=bool(fd and fd>today())
    rows=[]
    for l in fs:
        lid=str(l.get('lead_id','')); s=str(l.get('status','New')); ps=str(l.get('payment_status','Not Started'))
        rows.append(f'<tr><td><b>{esc(lid)}</b></td><td><b>{esc(l.get("name"))}</b><br><small>{esc(l.get("phone"))}</small></td><td>{esc(l.get("email"))}</td><td>{esc(l.get("country"))}<br><small>{esc(l.get("course_interest"))}</small></td><td>{esc(s)}</td><td>{esc(ps)}</td><td>{esc(l.get("assigned_counsellor")) or "—"}</td><td>{esc(l.get("follow_up_date")) or "—"} {esc(l.get("follow_up_time"))}</td><td><form class="quick" method="post" action="/update-lead"><input type="hidden" name="lead_id" value="{esc(lid)}"><select name="status">{opts(STATUSES,s)}</select><select name="payment_status">{opts(PAYMENT_STATUSES,ps)}</select><button>Save</button></form><a class="view" href="/lead?id={esc(lid)}">Open full profile →</a></td></tr>')
    countries=sorted({str(l.get('country')) for l in leads if l.get('country')},key=str.lower); courses=sorted({str(l.get('course_interest')) for l in leads if l.get('course_interest')},key=str.lower); counsellors=sorted({str(l.get('assigned_counsellor')) for l in leads if l.get('assigned_counsellor')},key=str.lower)
    def pipe(s,c): return f'<a class="pipeline" href="{("/?"+urlencode({"status":s})) if s!="All" else "/"}"><span>{esc(s)}</span><b>{c}</b></a>'
    body=(f'<div class="notice">{esc(p.get("message",[""])[0])}</div>' if p.get("message",[""])[0] else '')+f'<div class="cards">'+''.join(f'<div class="card"><span>{esc(a)}</span><strong>{b}</strong></div>' for a,b in [('Total Leads',len(leads)),('New',sc.get('New',0)),('Interested',sc.get('Interested',0)),('Enrolled',sc.get('Enrolled',0)),('Follow-ups Today',due),('Overdue',over),('Upcoming',up),('Conversion',f"{round(sc.get("Enrolled",0)/len(leads)*100,1) if leads else 0}%"),('Total Final Fees',f'{fee:,.2f}'),('Total Collected',f'{paid:,.2f}'),('Total Outstanding',f'{bal:,.2f}')])+'</div>'
    body+=f'<div class="grid"><section class="panel"><h2>Admission Pipeline</h2>{pipe("All",len(leads))}{"".join(pipe(s,sc.get(s,0)) for s in STATUSES)}</section><section class="panel"><h2>Lead Sources</h2>{"".join(f"<div class=\"mini\"><span>{esc(k)}</span><b>{v}</b></div>" for k,v in sorted(src.items(),key=lambda x:(-x[1],x[0].lower()))) or "<span class=muted>No source data.</span>"}</section></div>'
    body+=f'<section class="filters"><h2>Advanced Search & Filters</h2><form method="get"><div class="filtergrid"><input name="q" value="{esc(p.get("q",[""])[0])}" placeholder="Global search"><input name="name" value="{esc(p.get("name",[""])[0])}" placeholder="Student name"><input name="lead_id" value="{esc(p.get("lead_id",[""])[0])}" placeholder="Lead ID"><input name="phone" value="{esc(p.get("phone",[""])[0])}" placeholder="Phone"><input name="email" value="{esc(p.get("email",[""])[0])}" placeholder="Email"><select name="course"><option value="">All courses</option>{opts(courses,p.get("course",[""])[0])}</select><select name="country"><option value="">All countries</option>{opts(countries,p.get("country",[""])[0])}</select><select name="status"><option value="">All statuses</option>{opts(STATUSES,p.get("status",[""])[0])}</select><select name="payment_status"><option value="">All payment statuses</option>{opts(PAYMENT_STATUSES,p.get("payment_status",[""])[0])}</select><select name="source"><option value="">All sources</option>{opts(SOURCES,p.get("source",[""])[0])}</select><select name="counsellor"><option value="">All counsellors</option>{opts(counsellors,p.get("counsellor",[""])[0])}</select><input type="date" name="created_date" value="{esc(p.get("created_date",[""])[0])}"><input type="date" name="follow_up_date" value="{esc(p.get("follow_up_date",[""])[0])}"></div><div class="actions"><button>Search / Filter</button><a class="clear" href="/">Clear</a></div></form></section><section class="tablewrap"><table><thead><tr><th>Lead ID</th><th>Student</th><th>Email</th><th>Country / Course</th><th>Status</th><th>Payment</th><th>Counsellor</th><th>Follow-up</th><th>Quick Actions</th></tr></thead><tbody>{"".join(rows) or '<tr><td colspan="9" class="empty">No leads match.</td></tr>'}</tbody></table></section><p class="muted">Showing {len(fs)} of {len(leads)} leads. Data: {esc(LEADS)}</p>'
    return page('Lead Manager','dashboard',body)

def counselling_page(p):
    leads=all_leads(); q=p.get('q',[''])[0].lower().strip(); co=p.get('counsellor',[''])[0].lower().strip(); out=p.get('outcome',[''])[0].lower().strip(); df=p.get('date',[''])[0].strip(); sessions=[]; names=set()
    for l in leads:
        for s in hist(l,'counselling_history'):
            x=dict(s); x.update(_lid=str(l.get('lead_id','')),_name=str(l.get('name','')),_phone=str(l.get('phone','')),_country=str(l.get('country','')),_course=str(l.get('course_interest',''))); sessions.append(x)
            if x.get('counsellor'): names.add(str(x['counsellor']))
    work=[]
    for s in sessions:
        text=' '.join(str(s.get(k,'')) for k in ('_lid','_name','_phone','_country','_course','counsellor','mode','outcome','notes')).lower()
        if q and q not in text: continue
        if co and str(s.get('counsellor','')).lower()!=co: continue
        if out and str(s.get('outcome','')).lower()!=out: continue
        if df and str(s.get('counselling_date',''))!=df: continue
        work.append(s)
    work.sort(key=lambda s:(str(s.get('counselling_date','')),str(s.get('counselling_time',''))),reverse=True)
    rows=''.join(f'<tr><td><b>{esc(s.get("_lid"))}</b></td><td><b>{esc(s.get("_name"))}</b><br><small>{esc(s.get("_phone"))}</small></td><td>{esc(s.get("_country"))}<br><small>{esc(s.get("_course"))}</small></td><td>{esc(s.get("counselling_date"))}<br><small>{esc(s.get("counselling_time"))}</small></td><td>{esc(s.get("counsellor")) or "Unassigned"}</td><td>{esc(s.get("mode"))}</td><td><span class="badge">{esc(s.get("outcome"))}</span></td><td>{esc(s.get("notes")) or "—"}<br><small>Next: {esc(s.get("next_follow_up_date"))} {esc(s.get("next_follow_up_time"))}</small></td><td><a class="view" href="/lead?id={esc(s.get("_lid"))}">Open</a></td></tr>' for s in work)
    body=(f'<div class="notice">{esc(p.get("message",[""])[0])}</div>' if p.get("message",[""])[0] else '')+f'<div class="cards"><div class="card"><span>Total Sessions</span><strong>{len(sessions)}</strong></div><div class="card"><span>Today</span><strong>{sum(str(s.get("counselling_date",""))==today() for s in sessions)}</strong></div><div class="card"><span>Pending / Call Back</span><strong>{sum(str(s.get("outcome","")).lower() in {"pending","call back"} for s in sessions)}</strong></div><div class="card"><span>Enrolled</span><strong>{sum(str(s.get("outcome","")).lower()=="enrolled" for s in sessions)}</strong></div></div><section class="toolbar"><form style="display:flex;gap:8px;flex-wrap:wrap" method="get"><input name="q" value="{esc(p.get("q",[""])[0])}" placeholder="Search student, lead ID, phone, course..." style="min-width:280px"><select name="counsellor"><option value="">All counsellors</option>{opts(sorted(names,key=str.lower),p.get("counsellor",[""])[0])}</select><select name="outcome"><option value="">All outcomes</option>{opts(COUNSELLING_OUTCOMES,p.get("outcome",[""])[0])}</select><input type="date" name="date" value="{esc(df)}"><button>Search</button><a class="clear" href="/counselling">Clear</a></form></section><section class="tablewrap"><table><thead><tr><th>Lead ID</th><th>Student</th><th>Country / Course</th><th>Date / Time</th><th>Counsellor</th><th>Mode</th><th>Outcome</th><th>Notes / Next</th><th>Action</th></tr></thead><tbody>{rows or '<tr><td colspan="9" class="empty">No counselling sessions found.</td></tr>'}</tbody></table></section>'
    return page('Counselling Manager','counselling',body)

def fstate(l):
    x=str(l.get('follow_up_date','')).strip()
    if not x or not vdate(x): return 'none'
    return 'overdue' if x<today() else 'today' if x==today() else 'upcoming'

def followups_page(p):
    mode=p.get('filter',['today'])[0]
    if mode not in {'overdue','today','upcoming','all'}: mode='today'
    leads=all_leads(); counts={x:0 for x in ('overdue','today','upcoming')}
    for l in leads:
        s=fstate(l)
        if s in counts: counts[s]+=1
    work=[l for l in leads if fstate(l)!='none' and (mode=='all' or fstate(l)==mode)]
    work.sort(key=lambda l:(str(l.get('follow_up_date','9999-12-31')),str(l.get('follow_up_time','23:59'))))
    rows=''.join(f'<tr><td><b>{esc(l.get("lead_id"))}</b></td><td><b>{esc(l.get("name"))}</b><br><small>{esc(l.get("phone"))}</small></td><td>{esc(l.get("country"))}<br><small>{esc(l.get("course_interest"))}</small></td><td><span class="badge {fstate(l)}">{fstate(l).title()}</span><br>{esc(l.get("follow_up_date"))}<br><small>{esc(l.get("follow_up_time"))}</small></td><td>{esc(l.get("assigned_counsellor")) or "Unassigned"}</td><td>{esc(l.get("status"))}</td><td><form method="post" action="/follow-up-action"><input type="hidden" name="lead_id" value="{esc(l.get("lead_id"))}"><select name="outcome">{opts(FOLLOWUP_OUTCOMES,'Contacted')}</select><input name="counsellor" placeholder="Counsellor" value="{esc(l.get("assigned_counsellor"))}"><input type="date" name="next_follow_up_date"><input type="time" name="next_follow_up_time"><textarea name="notes" placeholder="Notes"></textarea><button>Save Follow-up</button></form></td><td><a class="view" href="/lead?id={esc(l.get("lead_id"))}">Open</a></td></tr>' for l in work)
    body=(f'<div class="notice">{esc(p.get("message",[""])[0])}</div>' if p.get("message",[""])[0] else '')+f'<div class="cards">'+''.join(f'<div class="card"><span>{x.title()}</span><strong>{counts[x]}</strong></div>' for x in counts)+f'<div class="card"><span>All Scheduled</span><strong>{sum(counts.values())}</strong></div></div><section class="toolbar"><div class="actions"><a class="clear" href="/follow-ups?filter=overdue">Overdue</a><a class="clear" href="/follow-ups?filter=today">Today</a><a class="clear" href="/follow-ups?filter=upcoming">Upcoming</a><a class="clear" href="/follow-ups?filter=all">All</a></div></section><section class="tablewrap"><table><thead><tr><th>Lead</th><th>Student</th><th>Country / Course</th><th>Due</th><th>Counsellor</th><th>Status</th><th>Complete Follow-up</th><th>Open</th></tr></thead><tbody>{rows or "<tr><td colspan=8 class=empty>No follow-ups in this view.</td></tr>"}</tbody></table></section>'
    return page('Follow-up Manager','followups',body)

def lead_page(l,msg=''):
    if not l: return page('Lead Not Found','dashboard','<section class="panel"><h2>Lead not found</h2><a class="back" href="/">Back</a></section>')
    recalc(l); lid=str(l.get('lead_id','')); currency=str(l.get('currency','INR')); ch=hist(l,'counselling_history'); fh=hist(l,'follow_up_history'); ph=hist(l,'payment_history')
    timeline=[(str(l.get('updated_at','')),'Lead record updated','CRM')]
    if l.get('created_at'): timeline.append((str(l['created_at']),'Lead created','CRM'))
    if l.get('last_contacted_at'): timeline.append((str(l['last_contacted_at']),'Student contacted','CRM'))
    timeline += [(str(s.get('counselling_date',''))+' '+str(s.get('counselling_time','')),f'Counselling — {s.get("outcome","")}',f'Counsellor: {s.get("counsellor") or "Unassigned"}') for s in ch]
    timeline += [(str(f.get('action_at','')),f'Follow-up — {f.get("outcome","")}',f'Counsellor: {f.get("counsellor") or "Unassigned"}') for f in fh]
    timeline += [(str(p.get('recorded_at','')),f'Payment — {p.get("amount",0)} {currency}',str(p.get('payment_mode',''))) for p in ph]
    timeline.sort(reverse=True)
    cr=f'<section class="panel"><h3>CRM Management</h3><form method="post" action="/update-lead"><input type="hidden" name="lead_id" value="{esc(lid)}"><div class="editgrid"><div><label>Status</label><select name="status">{opts(STATUSES,l.get("status","New"))}</select></div><div><label>Payment Status</label><select name="payment_status">{opts(PAYMENT_STATUSES,l.get("payment_status","Not Started"))}</select></div><div><label>Source</label><select name="source">{opts(SOURCES,l.get("source","Other"))}</select></div><div><label>Counsellor</label><input name="assigned_counsellor" value="{esc(l.get("assigned_counsellor"))}"></div><div><label>Follow-up Date</label><input type="date" name="follow_up_date" value="{esc(l.get("follow_up_date"))}"></div><div><label>Follow-up Time</label><input type="time" name="follow_up_time" value="{esc(l.get("follow_up_time"))}"></div><div class="full"><label>Follow-up Notes</label><textarea name="follow_up_notes">{esc(l.get("follow_up_notes"))}</textarea></div></div><div class="actions"><button>Save CRM Changes</button></div></form></section>'
    paybox=f'<section class="panel"><h3>Payment Management</h3><form method="post" action="/set-fee"><input type="hidden" name="lead_id" value="{esc(lid)}"><div class="editgrid"><div><label>Base Fee</label><input type="number" step="0.01" name="base_fee" value="{esc(l.get("base_fee",0))}"></div><div><label>Discount</label><input type="number" step="0.01" name="discount" value="{esc(l.get("discount",0))}"></div><div><label>Currency</label><input name="currency" value="{esc(currency)}"></div><div><label>Converted Amount</label><input type="number" step="0.01" name="converted_amount" value="{esc(l.get("converted_amount",0))}"></div></div><div class="actions"><button>Save Fee Details</button></div></form><hr><form method="post" action="/record-payment"><input type="hidden" name="lead_id" value="{esc(lid)}"><div class="editgrid"><div><label>Payment Amount</label><input type="number" step="0.01" min="0" name="amount" required></div><div><label>Payment Mode</label><select name="payment_mode">{opts(PAYMENT_MODES,'Online')}</select></div><div><label>Reference ID</label><input name="transaction_id"></div><div><label>Payment Date</label><input type="date" name="payment_date" value="{today()}"></div><div class="full"><label>Notes</label><textarea name="notes"></textarea></div></div><div class="actions"><button>Record Payment</button></div></form><h3>Payment History</h3>{('<div class="tablewrap"><table><tr><th>ID</th><th>Date</th><th>Amount</th><th>Mode</th><th>Reference</th></tr>'+''.join(f'<tr><td>{esc(p.get("payment_id"))}</td><td>{esc(p.get("payment_date"))}</td><td>{esc(p.get("amount"))} {esc(currency)}</td><td>{esc(p.get("payment_mode"))}</td><td>{esc(p.get("transaction_id")) or "—"}</td></tr>' for p in reversed(ph))+'</table></div>') if ph else '<p class="muted">No payments recorded.</p>'}</section>'
    body=f'<a class="back" href="/">← Back to Lead Manager</a>{("<div class=notice>"+esc(msg)+"</div>") if msg else ""}<section class="hero"><div><h2>{esc(l.get("name"))}</h2><p>Lead ID: <b>{esc(lid)}</b> · {esc(l.get("course_interest"))}</p></div><span class="badge">{esc(l.get("status","New"))}</span></section><div class="grid"><div><section class="panel"><h3>Student Information</h3><div class="info">'+''.join(f'<div class="item"><span>{esc(a)}</span><strong>{esc(l.get(k)) or "—"}</strong></div>' for a,k in [('Lead ID','lead_id'),('Name','name'),('Phone','phone'),('Email','email'),('Country','country'),('Language','preferred_language'),('Course','course_interest'),('Education','education'),('Source','source'),('Payment Status','payment_status')])+f'</div></section><section class="panel"><h3>Fee & Payment Summary</h3><div class="finance">'+''.join(f'<div class="fin"><span>{a}</span><strong>{esc(l.get(k,0))} {esc(currency)}</strong></div>' for a,k in [('Base Fee','base_fee'),('Discount','discount'),('Final Fee','final_fee'),('Total Paid','total_paid'),('Balance','balance_amount'),('Payment Status','payment_status')])+f'</div></section><section class="panel"><h3>Enquiry & Notes</h3><div class="item"><span>Original Enquiry</span><strong>{esc(l.get("message")) or "—"}</strong></div><div class="item"><span>Follow-up Notes</span><strong>{esc(l.get("follow_up_notes")) or "—"}</strong></div></section><section class="panel"><h3>New Counselling Session</h3><form method="post" action="/add-counselling"><input type="hidden" name="lead_id" value="{esc(lid)}"><div class="editgrid"><div><label>Counsellor</label><input name="counsellor" value="{esc(l.get("assigned_counsellor"))}"></div><div><label>Mode</label><select name="mode">{opts(COUNSELLING_MODES,'Phone')}</select></div><div><label>Date</label><input type="date" name="counselling_date" value="{today()}"></div><div><label>Time</label><input type="time" name="counselling_time"></div><div><label>Outcome</label><select name="outcome">{opts(COUNSELLING_OUTCOMES,'Pending')}</select></div><div><label>Next Date</label><input type="date" name="next_follow_up_date"></div><div><label>Next Time</label><input type="time" name="next_follow_up_time"></div><div class="full"><label>Notes</label><textarea name="notes"></textarea></div></div><div class="actions"><button>Save Counselling Session</button></div></form></section><section class="panel"><h3>Counselling History</h3>{('<div class="tablewrap"><table><tr><th>Date</th><th>Time</th><th>Counsellor</th><th>Mode</th><th>Outcome</th><th>Notes</th><th>Next</th></tr>'+''.join(f'<tr><td>{esc(s.get("counselling_date"))}</td><td>{esc(s.get("counselling_time"))}</td><td>{esc(s.get("counsellor"))}</td><td>{esc(s.get("mode"))}</td><td>{esc(s.get("outcome"))}</td><td>{esc(s.get("notes"))}</td><td>{esc(s.get("next_follow_up_date"))} {esc(s.get("next_follow_up_time"))}</td></tr>' for s in ch)+'</table></div>') if ch else '<p class="muted">No counselling sessions recorded.</p>'}</section><section class="panel"><h3>Activity Timeline</h3><div class="timeline">'+''.join(f'<div class="event"><div class="dot"></div><b>{esc(t)}</b><div class="muted">{esc(w)} · {esc(a)}</div></div>' for w,t,a in timeline)+'</div></section></div><div>{cr}{paybox}</div></div>'
    return page(f'{lid} — Lead Profile','dashboard',body)

def err(e): return page('Server Error','dashboard',f'<section class="panel"><h2>Server error</h2><p>{esc(e)}</p><a class="back" href="/">Back</a></section>')

class Handler(BaseHTTPRequestHandler):
    def log_message(self,fmt,*args): print('[CRM]',fmt%args)
    def html(self,x,status=200):
        b=x.encode(); self.send_response(status); self.send_header('Content-Type','text/html; charset=utf-8'); self.send_header('Content-Length',str(len(b))); self.end_headers(); self.wfile.write(b)
    def redirect(self,u): self.send_response(303); self.send_header('Location',u); self.end_headers()
    def data(self):
        n=int(self.headers.get('Content-Length','0') or 0); return parse_qs(self.rfile.read(n).decode(),keep_blank_values=True)
    def do_GET(self):
        try:
            u=urlparse(self.path); p=parse_qs(u.query,keep_blank_values=True)
            if u.path=='/brand-logo.svg':
                b=BRAND_LOGO_SVG.encode('utf-8')
                self.send_response(200)
                self.send_header('Content-Type','image/svg+xml; charset=utf-8')
                self.send_header('Content-Length',str(len(b)))
                self.end_headers()
                self.wfile.write(b)
                return
            if u.path=='/': return self.html(dashboard(p))
            if u.path=='/counselling': return self.html(counselling_page(p))
            if u.path=='/follow-ups': return self.html(followups_page(p))
            if u.path=='/lead':
                l=lead(p.get('id',[''])[0]); return self.html(lead_page(l,p.get('message',[''])[0]),200 if l else 404)
            self.html('<h1>404 - Not Found</h1>',404)
        except Exception as e: self.html(err(e),500)
    def do_POST(self):
        try:
            u=urlparse(self.path); d=self.data(); lid=d.get('lead_id',[''])[0].strip()
            if u.path=='/update-lead':
                l=lead(lid)
                if not l: return self.html('<h1>Lead not found</h1>',404)
                st=d.get('status',[l.get('status','New')])[0]; ps=d.get('payment_status',[l.get('payment_status','Not Started')])[0]; src=d.get('source',[l.get('source','Other')])[0]; fd=d.get('follow_up_date',[''])[0]; ft=d.get('follow_up_time',[''])[0]
                if st not in STATUSES or ps not in PAYMENT_STATUSES or src not in SOURCES or not vdate(fd) or not vtime(ft): return self.html('<h1>Invalid CRM values</h1>',400)
                db=load(); db[lid].update(status=st,payment_status=ps,source=src,follow_up_date=fd,follow_up_time=ft,assigned_counsellor=d.get('assigned_counsellor',[''])[0].strip(),follow_up_notes=d.get('follow_up_notes',[''])[0].strip(),updated_at=now());
                if st in {'Contacted','Counselling','Interested','Application','Payment Pending','Enrolled'}: db[lid]['last_contacted_at']=now()
                save(db); return self.redirect('/?message=Lead+updated+successfully')
            if u.path=='/add-counselling':
                if not lead(lid): return self.html('<h1>Lead not found</h1>',404)
                cd=d.get('counselling_date',[''])[0]; ct=d.get('counselling_time',[''])[0]; nd=d.get('next_follow_up_date',[''])[0]; nt=d.get('next_follow_up_time',[''])[0]
                if not all((vdate(cd),vtime(ct),vdate(nd),vtime(nt))): return self.html('<h1>Invalid counselling/follow-up date or time</h1>',400)
                add_counselling(lid,d.get('counsellor',[''])[0],cd,ct,d.get('mode',['Phone'])[0],d.get('outcome',['Pending'])[0],d.get('notes',[''])[0],nd,nt); return self.redirect('/lead?'+urlencode({'id':lid,'message':'Counselling session saved successfully'}))
            if u.path=='/follow-up-action':
                if not lead(lid): return self.html('<h1>Lead not found</h1>',404)
                nd=d.get('next_follow_up_date',[''])[0]; nt=d.get('next_follow_up_time',[''])[0]
                if not vdate(nd) or not vtime(nt): return self.html('<h1>Invalid follow-up date/time</h1>',400)
                add_followup(lid,d.get('outcome',['Contacted'])[0],d.get('notes',[''])[0],nd,nt,d.get('counsellor',[''])[0]); return self.redirect('/follow-ups?filter=today&message=Follow-up+saved+successfully')
            if u.path=='/set-fee':
                if not set_fee(lid,d.get('base_fee',['0'])[0],d.get('discount',['0'])[0],d.get('currency',['INR'])[0],d.get('converted_amount',['0'])[0]): return self.html('<h1>Invalid fee details</h1>',400)
                return self.redirect('/lead?'+urlencode({'id':lid,'message':'Fee details saved successfully'}))
            if u.path=='/record-payment':
                l=lead(lid); a=dec(d.get('amount',['0'])[0])
                if not l: return self.html('<h1>Lead not found</h1>',404)
                if a<=0 or (dec(l.get('final_fee'))>0 and a>dec(l.get('balance_amount'))): return self.html('<h1>Invalid payment amount or balance exceeded</h1>',400)
                if not pay(lid,a,d.get('payment_mode',['Online'])[0],d.get('transaction_id',[''])[0],d.get('payment_date',[''])[0],d.get('notes',[''])[0]): return self.html('<h1>Payment could not be recorded</h1>',400)
                return self.redirect('/lead?'+urlencode({'id':lid,'message':'Payment recorded successfully'}))
            self.html('<h1>404 - Not Found</h1>',404)
        except Exception as e: self.html(err(e),500)

def main():
    ensure(); print('='*65); print('Sayyed EdVantage CRM — REBUILT'); print(f'Dashboard: http://{HOST}:{PORT}'); print(f'Data: {LEADS}'); print('Press Ctrl+C to stop.'); print('='*65)
    s=ThreadingHTTPServer((HOST,PORT),Handler)
    try: s.serve_forever()
    except KeyboardInterrupt: print('\nCRM stopped.')
    finally: s.server_close()
if __name__=='__main__': main()
