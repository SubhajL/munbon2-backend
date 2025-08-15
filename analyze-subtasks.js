const fs = require('fs');

// Read tasks.json
const tasksData = JSON.parse(fs.readFileSync('./tasks/tasks.json', 'utf8'));
const tasks = tasksData.master.tasks;

console.log('# DETAILED SUBTASK ANALYSIS\n');

// Find tasks with subtasks
const tasksWithSubtasks = tasks.filter(task => task.subtasks && task.subtasks.length > 0);

console.log('## TASKS WITH SUBTASKS\n');

tasksWithSubtasks.forEach(task => {
  const completedSubtasks = task.subtasks.filter(st => st.status === 'done' || st.status === 'completed').length;
  const totalSubtasks = task.subtasks.length;
  const percentage = Math.round((completedSubtasks / totalSubtasks) * 100);
  
  console.log(`### Task ${task.id}: ${task.title}`);
  console.log(`Status: ${task.status} | Priority: ${task.priority}`);
  console.log(`Subtask Progress: ${completedSubtasks}/${totalSubtasks} (${percentage}%)\n`);
  
  task.subtasks.forEach(subtask => {
    const status = subtask.status === 'done' || subtask.status === 'completed' ? '✅' : 
                   subtask.status === 'in_progress' ? '🔄' : '⏳';
    console.log(`  ${status} ${task.id}.${subtask.id}: ${subtask.title}`);
    console.log(`     Status: ${subtask.status}`);
    if (subtask.dependencies && subtask.dependencies.length > 0) {
      console.log(`     Dependencies: ${subtask.dependencies.join(', ')}`);
    }
    console.log('');
  });
  console.log('---\n');
});