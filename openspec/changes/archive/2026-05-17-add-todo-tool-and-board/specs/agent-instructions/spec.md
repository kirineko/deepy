## ADDED Requirements

### Requirement: Todo Tool Guidance

Deepy SHALL instruct the model when and how to use the `todo_write` tool.

#### Scenario: User request is complex

- **WHEN** the user's request requires multiple meaningful steps, touches
  multiple files, or includes several distinct deliverables
- **THEN** Deepy SHALL guide the model to create or update a todo plan with
  `todo_write`
- **AND** the guidance SHALL tell the model to mark the current task
  `in_progress` before working on it

#### Scenario: User request is simple

- **WHEN** the user's request is a simple question, a single obvious edit, or a
  task that does not benefit from progress tracking
- **THEN** Deepy SHALL guide the model to skip `todo_write`
- **AND** it SHALL proceed directly without creating todo noise

#### Scenario: Real progress is made

- **WHEN** the model completes a meaningful todo item or discovers a necessary
  new task
- **THEN** Deepy SHALL guide the model to update the complete todo list with
  `todo_write`
- **AND** it SHALL avoid repeatedly calling `todo_write` when no task state has
  changed

#### Scenario: Model is ready to finish

- **WHEN** the model is about to provide the final answer for a task that used
  todos
- **THEN** Deepy SHALL guide the model to reconcile the todo plan so completed
  work is marked `completed`
- **AND** any unfinished work SHALL be clearly represented in the final answer
  rather than silently left ambiguous
