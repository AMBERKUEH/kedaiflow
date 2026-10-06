import { useState } from 'react';
import { Forecast, money, dateLabel } from '../lib/api';

export function Companion({small=false}: {small?:boolean}) {
  return <svg className={small?'companion small':'companion'} viewBox="0 0 220 190" role="img" aria-label="Kiki, your little shopkeeping companion">
    <ellipse cx="115" cy="174" rx="61" ry="9" fill="#143e3530"/>
    <path d="M61 125 Q36 135 32 115 M163 121 Q191 130 193 107" fill="none" stroke="#214b42" strokeWidth="10" strokeLinecap="round"/>
    <path d="M86 159 L81 173 M144 157 L151 172" stroke="#214b42" strokeWidth="11" strokeLinecap="round"/>
    <rect x="55" y="44" width="119" height="116" rx="33" fill="#fff7df" stroke="#234b43" strokeWidth="3"/>
    <path d="M61 63 Q110 40 169 65 L171 92 Q109 67 58 89Z" fill="#70b89d"/>
    <path d="M75 49 C77 9 151 9 154 51" fill="none" stroke="#234b43" strokeWidth="7"/>
    <path d="M87 45 C89 21 139 21 142 47" fill="none" stroke="#b8dac2" strokeWidth="5"/>
    <circle cx="87" cy="103" r="4.5" fill="#203d36"/><circle cx="139" cy="103" r="4.5" fill="#203d36"/>
    <path d="M105 112 Q114 122 123 111" fill="none" stroke="#203d36" strokeWidth="3.5" strokeLinecap="round"/>
    <ellipse cx="76" cy="113" rx="8" ry="4" fill="#edc2a1"/><ellipse cx="150" cy="113" rx="8" ry="4" fill="#edc2a1"/>
    <rect x="111" y="128" width="49" height="37" rx="5" transform="rotate(-12 135 146)" fill="#e4ab59" stroke="#234b43" strokeWidth="2"/>
    <path d="M124 133 L144 129 M126 141 L146 137 M128 149 L139 147" stroke="#fff8e5" strokeWidth="3" strokeLinecap="round"/>
    <path d="M178 42 L182 31 M188 47 L199 44 M174 30 L172 22" stroke="#fff8e8" strokeWidth="3" strokeLinecap="round"/>
  </svg>;
}

export function CashChart({forecast,compact=false}: {forecast:Forecast;compact?:boolean}) {
  const [selected, setSelected] = useState<number|null>(null);
  const values = forecast.daily.map(d=>d.closing_minor);
  if (values.every(v=>v===null)) return <div className="empty">Add an opening balance and its date to calculate the cash calendar.</div>;
  const buffer = forecast.buffer_minor??100000; const low = Math.min(0,...values.map(v=>v??0)); const high = Math.max(buffer,...values.map(v=>v??0));
  const range = high-low || 1;
  const x = (i:number) => 58 + i/(values.length-1)*670;
  const y = (v:number) => 23+(high-v)/range*155;
  const points = values.map((v,i)=>`${x(i)},${y(v??0)}`).join(' ');
  const area = `58,194 ${points} 728,194`;
  const picked = selected===null?null:forecast.daily[selected];
  return <div className={'chart '+(compact?'compact':'')}>
    <svg viewBox="0 0 760 235" role="img" aria-label={`${forecast.daily.length}-day cash forecast. Lowest balance ${money(forecast.trough_minor)} on ${forecast.trough_date}. Detailed table available below.`}>
      <defs><linearGradient id="cashFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#8cbea5" stopOpacity=".4"/><stop offset="100%" stopColor="#c4dccc" stopOpacity=".06"/></linearGradient></defs>
      {[0,.5,1].map(t=><g key={t}><line x1="58" y1={23+t*155} x2="730" y2={23+t*155} stroke="#e8e9e1" strokeDasharray="3 5"/><text x="0" y={27+t*155} fill="#87928b" fontSize="11">{Math.round((high-t*range)/100000)}k</text></g>)}
      <polygon points={area} fill="url(#cashFill)"/>
      <line x1="58" y1={y(buffer)} x2="730" y2={y(buffer)} stroke="#d3a45e" strokeDasharray="5 5"/>
      <polyline points={points} fill="none" stroke="#3e8066" strokeWidth="3" strokeLinejoin="round" strokeLinecap="round"/>
      {values.map((v,i)=><g key={i}><circle cx={x(i)} cy={y(v??0)} r={selected===i?5:2.5} fill={selected===i?'#173c35':'#5b937a'}/><rect x={x(i)-11} y="5" width="22" height="196" fill="transparent" onMouseEnter={()=>setSelected(i)} onClick={()=>setSelected(i)}/></g>)}
      {[0,Math.floor(values.length/3),Math.floor(values.length*2/3),values.length-1].map(i=><text key={i} x={x(i)} y="223" textAnchor="middle" fill="#87928b" fontSize="11">{dateLabel(forecast.daily[i].date)}</text>)}
    </svg>
    <div className="chart-caption">{picked ? `${dateLabel(picked.date)} · Forecast ${money(picked.closing_minor)} · In ${money(picked.inflow_minor)} · Out ${money(picked.outflow_minor)}` : 'Forecast includes expected receipts and recorded obligations.'}<span><i/> {money(buffer)} buffer</span></div>
    {!compact&&<details><summary>View daily amounts and their sources</summary><div className="table-scroll"><table><thead><tr><th>Date</th><th>Expected in</th><th>Expected out</th><th>Closing forecast</th><th>Source</th></tr></thead><tbody>{forecast.daily.map(day=><tr key={day.date}><td>{dateLabel(day.date)}</td><td>{money(day.inflow_minor)}</td><td>{money(day.outflow_minor)}</td><td>{money(day.closing_minor)}</td><td>{day.movements.map(m=>`${m.label} (${m.basis})`).join(', ')||'Carried forward'}</td></tr>)}</tbody></table></div></details>}
  </div>;
}

