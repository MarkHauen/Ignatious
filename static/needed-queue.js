let needs=[];
const $=id=>document.getElementById(id);
function renderNeeds(){
  const q=$('need-search').value.toLowerCase();
  const visible=needs.filter(n=>[n.title,n.description,n.resolution].some(v=>(v||'').toLowerCase().includes(q)));
  N.render($('needed-list'),visible,loadNeeds,true);
  $('needed-summary').textContent=`${visible.length} needed items · all months and nesting levels. Decisions remain separate from task completion.`;
}
async function loadNeeds(){
  const params=new URLSearchParams({project_id:'1'}),state=$('need-filter').value;
  if(state==='open')params.set('open_only','true');else if(state!=='all')params.set('state',state);
  if($('kind-filter').value)params.set('kind',$('kind-filter').value);
  if($('epic-filter').value)params.set('epic_id',$('epic-filter').value);
  needs=await I.api(`/api/needed-tasks/?${params}`);renderNeeds();
}
['need-filter','kind-filter','epic-filter'].forEach(id=>$(id).onchange=()=>I.run(loadNeeds));
$('need-search').oninput=renderNeeds;
I.run(async()=>{await I.refs();I.options($('epic-filter'),[['','All epics'],...I.epics.map(e=>[e.id,e.title])],'');await loadNeeds();});
