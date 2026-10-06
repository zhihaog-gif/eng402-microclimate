from pathlib import Path
import io, json
import argparse
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Rectangle, FancyArrowPatch

ROOT = Path(__file__).resolve().parent
INPUT = ROOT/'data/main'
OUT = ROOT/'figures'
parser=argparse.ArgumentParser(description='Regenerate the seven reviewed thesis figures from original input files.')
parser.add_argument('--input-dir',type=Path,default=INPUT)
parser.add_argument('--output-dir',type=Path,default=OUT)
args=parser.parse_args()
INPUT=args.input_dir
OUT=args.output_dir
OUT.mkdir(exist_ok=True)
IDS = dict(A=1623979917, B=1611764737, C=1549287845, D=1549410049)
COLORS = ['#0072BD','#D95319','#009973','#7E2F8E']
CUTOFF = pd.Timestamp('2026-09-20 09:42:37')
BATTERY_START = pd.Timestamp('2026-09-19 22:56:00')
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False})

def read_input(day):
    p=INPUT/f'sensor_data_2026-09-{day:02d}.csv'
    raw=p.read_bytes()
    t=pd.read_excel(io.BytesIO(raw),engine='openpyxl') if raw[:2]==b'PK' else pd.read_csv(p)
    t['time']=pd.to_datetime(t['receive_time'])
    return t

def save(fig, name):
    fig.savefig(OUT/(name+'.png'),dpi=300,bbox_inches='tight',facecolor='white')
    fig.savefig(OUT/(name+'.pdf'),bbox_inches='tight',facecolor='white')
    plt.close(fig)

def day_axis(ax, first, end):
    ticks=pd.date_range(first.normalize(),end.normalize(),freq='D')
    ax.set_xticks(ticks)
    ax.set_xticklabels([t.strftime('%d %b') for t in ticks])
    ax.set_xlim(first.normalize(),end)
    ax.grid(True,alpha=.18)

frames={d:read_input(d) for d in range(14,21)}
all_four=pd.concat([frames[d] for d in range(17,21)],ignore_index=True).sort_values('time')
trial=all_four[all_four['time']<=CUTOFF].copy()
assert len(trial)==217620
first=trial['time'].min(); last=trial['time'].max()
means=[]
fig,axs=plt.subplots(2,1,figsize=(8.2,6.2),sharex=True)
for (letter,nodeid),color in zip(IDS.items(),COLORS):
    s=trial[trial.node_id==nodeid].set_index('time')
    a=s[['temperature_c','pressure_hpa']].resample('5min').mean()
    a=a.reindex(pd.date_range(first.floor('5min'),last.floor('5min'),freq='5min'))
    a['node']=letter;means.append(a.reset_index(names='bin_start'))
    axs[0].plot(a.index,a.temperature_c,color=color,lw=1,label='Node '+letter)
    axs[1].plot(a.index,a.pressure_hpa,color=color,lw=1)
for ax in axs:day_axis(ax,first,CUTOFF)
axs[0].set_ylabel('Temperature (°C)');axs[1].set_ylabel('Pressure (hPa)')
axs[0].legend(loc='upper left',ncol=4,frameon=False,fontsize=9)
axs[1].set_xlabel('Gateway date · five-minute means')
fig.tight_layout();save(fig,'Figure_5_12_Main_Trial_Environmental_Records')
pd.concat(means).to_csv(OUT/'Figure_5_12_five_minute_means.csv',index=False)

bins=pd.date_range(first.floor('5min'),last.floor('5min'),freq='5min')
fig,ax=plt.subplots(figsize=(8.2,3.1))
occupancy=[]
for i,((letter,nodeid),color) in enumerate(zip(IDS.items(),COLORS)):
    occupied=trial.loc[trial.node_id==nodeid,'time'].dt.floor('5min').unique()
    flags=bins.isin(occupied)
    assert flags.sum()==908
    edges=np.diff(np.r_[False,flags,False].astype(int))
    for lo,hi in zip(np.flatnonzero(edges==1),np.flatnonzero(edges==-1)-1):

        ax.plot([max(bins[lo],first),min(bins[hi]+pd.Timedelta(minutes=5),CUTOFF)],
                [4-i,4-i],color=color,lw=4,solid_capstyle='butt')
    occupancy.append({'node':letter,'occupied_bins':int(flags.sum()),'total_bins':len(bins)})
day_axis(ax,first,CUTOFF)
ax.set_ylim(.5,4.5);ax.set_yticks([1,2,3,4],['Node D','Node C','Node B','Node A'])
ax.set_xlabel('Gateway date · at least one record per occupied five-minute bin')
ax.set_ylabel('Physical node');fig.tight_layout();save(fig,'Figure_5_13_Main_Trial_Reception_Activity')

fig,ax=plt.subplots(figsize=(8.2,3.1))
for letter,color in [('C',COLORS[2]),('D',COLORS[3])]:
    s=trial[(trial.node_id==IDS[letter])&(trial.time>=BATTERY_START)]
    assert len(s)==7758
    ax.plot([BATTERY_START,s.time.max()],[2 if letter=='C' else 1]*2,color=color,lw=5,solid_capstyle='butt')
ticks=[BATTERY_START,pd.Timestamp('2026-09-20 02:00'),pd.Timestamp('2026-09-20 06:00'),CUTOFF]
ax.set_xticks(ticks,['19 Sep 22:56','20 Sep 02:00','20 Sep 06:00','20 Sep 09:42'])
ax.set_xlim(BATTERY_START-pd.Timedelta(minutes=20),CUTOFF+pd.Timedelta(minutes=20))
ax.set_yticks([1,2],['Node D','Node C']);ax.set_ylim(.5,2.5)
ax.set_xlabel('Gateway clock · fully charged 3.7 V, 2600 mAh cells')
ax.grid(axis='x',alpha=.18);fig.tight_layout();save(fig,'Figure_5_2_Battery_Reporting_Interval')

daily=[]
for d,t in frames.items():
    if d==20:t=t[t.time<=CUTOFF]
    for letter,nodeid in IDS.items():
        s=t[t.node_id==nodeid].sort_values('time').copy()
        reset=(s.sequence.diff()<0)&(s.uptime_ms.diff()<0)

        if d==16 and letter=='A':
            repeated_start=(s.sequence==2)&(s.sequence.shift()==2)
            reset=reset|repeated_start
        groups=reset.cumsum()
        rec=exp=0
        for _,g in s.groupby(groups):
            seq=g.sequence.astype('int64');rec+=seq.nunique();exp+=int(seq.max()-seq.min()+1)
        daily.append(dict(day=d,node=letter,received=rec,expected=exp,pdr=100*rec/exp))
daily=pd.DataFrame(daily)
assert daily[(daily.day==16)&(daily.node=='A')].received.iloc[0]==632
fig,axs=plt.subplots(2,1,figsize=(8.2,5.6),sharex=True)
x=np.arange(7);width=.19
for i,(letter,color) in enumerate(zip(IDS,COLORS)):
    s=daily[daily.node==letter]
    axs[0].bar(x+(i-1.5)*width,s.received,width,color=color,label='Node '+letter)
    axs[1].plot(x,s.pdr,'o-',color=color,lw=1,ms=3)
axs[0].set_ylabel('Received records');axs[0].legend(ncol=4,frameon=False,fontsize=9,loc='upper center',bbox_to_anchor=(.5,1.18))
axs[1].set_ylabel('Sequence PDR (%)');axs[1].set_ylim(96.5,100.25)
axs[1].set_xticks(x,[f'{d} Sep' for d in range(14,21)])
axs[1].set_xlabel('File date · 20 Sep ends at 09:42:37')
for ax in axs:ax.grid(axis='y',alpha=.18)
fig.tight_layout();save(fig,'Figure_5_3_Daily_Reception_and_PDR')
daily.to_csv(OUT/'Figure_5_3_daily_delivery.csv',index=False)

baseline=frames[14];snapshot=pd.Timestamp('2026-09-14 21:55:00')
xy=np.array([[0,0],[10,0],[0,10],[10,10]],dtype=float)
vals=[];snapshot_rows=[]
for letter,nodeid in IDS.items():
    r=baseline[(baseline.node_id==nodeid)&(baseline.time<=snapshot)].sort_values('time').iloc[-1]
    vals.append(float(r.temperature_c));snapshot_rows.append({'node':letter,'receive_time':str(r.time),'temperature_c':float(r.temperature_c)})
vals=np.array(vals)
gx,gy=np.meshgrid(np.linspace(-1,11,100),np.linspace(-1,11,100))
dist=np.sqrt((gx[...,None]-xy[:,0])**2+(gy[...,None]-xy[:,1])**2)
weights=1/np.maximum(dist,1e-12)**2
gz=(weights*vals).sum(axis=-1)/weights.sum(axis=-1)
fig,ax=plt.subplots(figsize=(6.6,5))
im=ax.contourf(gx,gy,gz,levels=16,cmap='viridis')
fig.colorbar(im,ax=ax,label='Estimated temperature (°C)')
for (letter,_),(xx,yy),v in zip(IDS.items(),xy,vals):
    ax.plot(xx,yy,'wo',mec='black',ms=6)
    ax.annotate(f'Node {letter}\n{v:.2f} °C',(xx,yy),xytext=(-6 if xx==10 else 5,7),ha='right' if xx==10 else 'left',textcoords='offset points',fontsize=9,
                color='black',bbox=dict(facecolor='white',edgecolor='none',alpha=.85,pad=2))
ax.set_xlabel('Configured x');ax.set_ylabel('Configured y');ax.set_aspect('equal')
ax.set_title('IDW display · 14 Sep 2026, 21:55 gateway clock',fontsize=11)
fig.tight_layout();save(fig,'Figure_5_11_Traceable_IDW_Display')
pd.DataFrame(snapshot_rows).to_csv(OUT/'Figure_5_11_snapshot_inputs.csv',index=False)

fig,ax=plt.subplots(figsize=(9.2,7.5));ax.set_xlim(0,10);ax.set_ylim(0,9.1);ax.axis('off')
def box(x,y,w,h,label,fs=10):
    ax.add_patch(Rectangle((x,y),w,h,fill=False,lw=1.2))
    ax.text(x+w/2,y+h/2,label,ha='center',va='center',fontsize=fs)
def arrow(a,b,label=None):
    ax.add_patch(FancyArrowPatch(a,b,arrowstyle='-|>',mutation_scale=12,lw=1,color='black'))
    if label:ax.text((a[0]+b[0])/2+.12,(a[1]+b[1])/2,label,ha='left',va='center',fontsize=9)
for i,letter in enumerate(IDS):
    xx=.2+2.5*i;box(xx,8.15,2.1,.7,f'Node {letter}\nESP32 + BMP280')
    arrow((xx+1.05,8.15),(xx+1.05,7.8))
box(.2,7.2,9.6,.6,'painlessMesh Wi-Fi network')
arrow((5,7.2),(5,6.8));box(3.5,6.05,3,.75,'Dedicated ESP32 root')
arrow((5,6.05),(5,5.5),'USB serial')
ax.add_patch(Rectangle((.2,1.35),9.6,4.15,fill=False,lw=1.5,linestyle=(0,(5,3))))
ax.text(.45,5.17,'Raspberry Pi 3B',fontweight='bold',fontsize=11)
box(.7,3.8,2.5,.85,'Acquisition\nParse JSON and save CSV')
box(3.85,3.8,2.3,.85,'Local storage\nRaw and derived files')
box(6.8,3.8,2.5,.85,'Processing\nFlags, means and IDW')
arrow((5,5.5),(1.95,4.65))
arrow((3.2,4.225),(3.85,4.225));arrow((6.15,4.225),(6.8,4.225))
box(6.8,1.8,2.5,.85,'Flask dashboard')
arrow((8.05,3.8),(8.05,2.65))
box(.7,1.8,2.5,.85,'USB synchronisation')
arrow((3.85,3.8),(1.95,2.65))
box(.7,.15,2.5,.7,'External USB storage')
arrow((1.95,1.8),(1.95,.85))
box(6.8,.15,2.5,.7,'Browser on laptop')
arrow((8.05,1.8),(8.05,.85))
ax.text(8.18,1.05,'Local network',ha='left',va='center',fontsize=9)
fig.tight_layout();save(fig,'Figure_3_1_System_Architecture')

fig,ax=plt.subplots(figsize=(8.5,5.5));ax.set_xlim(0,10);ax.set_ylim(0,7);ax.axis('off')
box(.4,3.25,4,2.8,'ESP32 development board',11)
box(6,3.25,3.6,2.8,'BMP280 breakout',11)
for y,left,right in [(5.0,'3V3','VCC'),(4.55,'GND','GND'),(4.10,'GPIO 21','SDA'),(3.65,'GPIO 22','SCL')]:
    ax.plot([4.4,6],[y,y],color='black',lw=1)
    ax.text(4.25,y,left,ha='right',va='center',fontsize=9)
    ax.text(6.15,y,right,ha='left',va='center',fontsize=9)
box(.4,1.9,4, .85,'Node C and Node D\n3.7 V, 2600 mAh lithium cells',10)
arrow((2.4,2.75),(2.4,3.25),'Board battery input')
ax.text(6,2.25,'Node A and Node B used\ncontinuous external power.',fontsize=10,ha='left',va='center')
box(.4,.15,2.7,.75,'External Pi power');box(3.65,.15,2.7,.75,'Raspberry Pi 3B');box(7,.15,2.7,.75,'Dedicated root')
arrow((3.1,.525),(3.65,.525));arrow((7,.525),(6.35,.525))
ax.text(6.7,1.02,'USB serial',ha='center',fontsize=9)
fig.tight_layout();save(fig,'Figure_3_4_Wiring_and_Power_Connections')

(OUT/'analysis_metadata.json').write_text(json.dumps({'trial_first':str(first),'trial_last':str(last),
    'trial_cutoff':str(CUTOFF),'trial_records':len(trial),'occupancy':occupancy,'idw_inputs':snapshot_rows},indent=2))
print('Rebuilt seven figures from unchanged input files.',len(trial),'principal-trial records.')
