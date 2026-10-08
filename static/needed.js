const N = {
  edit(need, taskId, refresh) {
    const fields=[
      {name:'title',label:'Needed task title',required:true,max:300,value:need?.title},
      {name:'kind',label:'Type',options:['Decision','Investigation','Action'],value:need?.kind||'Action'},
      {name:'description',label:'Details / completion criteria',type:'textarea',value:need?.description}
    ];
    if(need)fields.push(
      {name:'state',label:'Follow-up state',options:[need.linked_task_id?'Linked':'Open','Resolved','Dismissed'],value:need.state},
      {name:'resolution',label:'Outcome / reason',type:'textarea',value:need.resolution}
    );
    return I.formDialog(need?'Review needed task':'Add needed task',fields,need?'Save review':'Add needed task',async values=>{
      if(need)values.expected_revision=need.revision;
      await I.api(need?`/api/needed-tasks/${need.id}`:`/api/tasks/${taskId}/needed-tasks`,need?'PATCH':'POST',values);
      await refresh();I.message('Needed task saved.');
    });
  },
  render(container, needs, refresh, showSource=false) {
    container.replaceChildren();
    if(!needs.length)container.append(I.el('p','No needed tasks in this view.','empty-state'));
    needs.forEach(need=>{
      const row=I.el('article',null,'needed-card');row.dataset.needId=need.id;
      const header=I.el('div',null,'needed-header');header.append(I.el('h3',need.title),I.el('span',`${need.kind} · ${need.state}`,'resolution-badge'));row.append(header);
      if(showSource){const source=I.el('a',`Source task #${need.task_id}`);source.href=I.taskLink({id:need.task_id});row.append(source);}
      if(need.description)row.append(I.el('p',need.description,'needed-copy'));
      if(need.resolution)row.append(I.el('p',`Outcome: ${need.resolution}`,'needed-copy'));
      const actions=I.el('div',null,'needed-actions');
      const edit=I.el('button','Edit / resolve','secondary-button');edit.type='button';edit.onclick=()=>this.edit(need,need.task_id,refresh);actions.append(edit);
      if(need.linked_task_id){
        const link=I.el('a',`Task #${need.linked_task_id} · ${need.linked_task_status}`,'secondary-button');link.href=I.taskLink({id:need.linked_task_id});actions.append(link);
        if(need.linked_task_status==='Complete'&&need.state==='Linked')row.append(I.el('p','Linked task is complete. Review its outcome before resolving this item.','field-help'));
      }else if(need.state==='Open'){
        const create=I.el('button','Create subtask','secondary-button');create.type='button';create.onclick=()=>I.run(async()=>{
          create.disabled=true;try{await I.api(`/api/needed-tasks/${need.id}/materialize`,'POST',{});await refresh();I.message('Follow-up subtask created.');}finally{create.disabled=false;}
        });actions.append(create);
        const link=I.el('button','Link existing task','secondary-button');link.type='button';link.onclick=()=>I.run(async()=>{
          const source=await I.api(`/api/tasks/${need.task_id}`);
          const candidates=await I.api(`/api/tasks/?project_id=${source.project_id}`);
          I.formDialog('Link existing work',[{name:'existing_task_id',label:'Existing task',required:true,options:[['','Choose a task'],...candidates.filter(t=>t.id!==need.task_id).map(t=>[t.id,`#${t.id} · ${t.title}`])]}],'Link task',async values=>{
            await I.api(`/api/needed-tasks/${need.id}/materialize`,'POST',{existing_task_id:Number(values.existing_task_id)});await refresh();I.message('Existing task linked.');
          });
        });actions.append(link);
      }
      row.append(actions);container.append(row);
    });
  }
};
