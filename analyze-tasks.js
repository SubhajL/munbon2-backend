const fs = require('fs');

// Read tasks.json
const tasksData = JSON.parse(fs.readFileSync('./tasks/tasks.json', 'utf8'));
const tasks = tasksData.master.tasks;

// Categorize tasks
const completed = [];
const pending = [];
const inProgress = [];

// Analyze each task
tasks.forEach(task => {
  const subtasks = task.subtasks || [];
  const completedSubtasks = subtasks.filter(st => st.status === 'done' || st.status === 'completed').length;
  const totalSubtasks = subtasks.length;
  
  const taskInfo = {
    id: task.id,
    title: task.title,
    status: task.status,
    priority: task.priority,
    subtasks: totalSubtasks,
    completedSubtasks: completedSubtasks,
    completionPercentage: totalSubtasks > 0 ? Math.round((completedSubtasks / totalSubtasks) * 100) : (task.status === 'done' ? 100 : 0)
  };
  
  if (task.status === 'done' || task.status === 'completed') {
    completed.push(taskInfo);
  } else if (totalSubtasks > 0 && completedSubtasks > 0 && completedSubtasks < totalSubtasks) {
    inProgress.push(taskInfo);
  } else {
    pending.push(taskInfo);
  }
});

// Output results
console.log('# MUNBON BACKEND PROJECT - TASK STATUS REPORT\n');
console.log(`Total Tasks: ${tasks.length}`);
console.log(`Completed: ${completed.length}`);
console.log(`In Progress: ${inProgress.length}`);
console.log(`Not Started: ${pending.length}\n`);

console.log('## ✅ COMPLETED TASKS\n');
completed.forEach(task => {
  console.log(`${task.id}. ${task.title} [Priority: ${task.priority}]`);
  if (task.subtasks > 0) {
    console.log(`   - Subtasks: ${task.completedSubtasks}/${task.subtasks} (100%)`);
  }
});

console.log('\n## 🔄 IN PROGRESS TASKS (with partial subtask completion)\n');
inProgress.forEach(task => {
  console.log(`${task.id}. ${task.title} [Priority: ${task.priority}]`);
  console.log(`   - Progress: ${task.completedSubtasks}/${task.subtasks} subtasks (${task.completionPercentage}%)`);
  
  // Show subtask details
  const taskData = tasks.find(t => t.id === task.id);
  if (taskData && taskData.subtasks) {
    taskData.subtasks.forEach(st => {
      const status = st.status === 'done' || st.status === 'completed' ? '✓' : '○';
      console.log(`     ${status} ${st.id}. ${st.title}`);
    });
  }
});

console.log('\n## ⏳ NOT STARTED TASKS\n');
pending.forEach(task => {
  console.log(`${task.id}. ${task.title} [Priority: ${task.priority}]`);
  if (task.subtasks > 0) {
    console.log(`   - ${task.subtasks} subtasks to complete`);
  }
});

// Summary by priority
console.log('\n## PRIORITY BREAKDOWN\n');
const priorities = { high: 0, medium: 0, low: 0 };
pending.forEach(task => {
  priorities[task.priority || 'medium']++;
});
console.log(`High Priority Pending: ${priorities.high}`);
console.log(`Medium Priority Pending: ${priorities.medium}`);
console.log(`Low Priority Pending: ${priorities.low}`);