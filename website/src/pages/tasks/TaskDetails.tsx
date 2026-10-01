import {
  Badge,
  DetailList,
  Drawer,
  NumberValue,
  Ratio,
  RawJson,
  SourceLink,
} from '../../shared/components'
import type { ResultRow } from '../../shared/types/benchmark'

export function TaskDetails({ task, onClose }: { task: ResultRow | null; onClose: () => void }) {
  return (
    <Drawer title={task?.taskId || 'Task details'} open={Boolean(task)} onClose={onClose}>
      {task && (
        <>
          <div className="drawer-badges">
            <Badge tone="accent" value={task.level} />
            <Badge value={task.language} />
            {task.missing && <Badge tone="neutral" value="Not submitted · Score 0" />}
            {task.buildSuccess !== null && (
              <Badge
                tone={task.buildSuccess ? 'success' : 'danger'}
                value={task.buildSuccess ? 'Build success' : 'Build failed'}
              />
            )}
          </div>
          <DetailList
            entries={[
              ['Project', task.project],
              ['Method', task.method],
              ['Model', task.model],
              ['Source', task.sourceType],
              ['Submitter', task.submitter || '—'],
              ['Submission coverage', <Ratio value={task.coverageRate} />],
              ['Scoring mode', task.scoringMode || '—'],
              ['Full pass', task.fullPass === null ? '—' : task.fullPass ? 'Yes' : 'No'],
              ['Test-pass ratio', <Ratio value={task.testPassRatio} />],
              ['Execution score', <NumberValue value={task.executionScore} />],
              ['Correctness', <NumberValue value={task.correctness} />],
              ['Faithfulness', <NumberValue value={task.faithfulness} />],
              ['Architecture', <NumberValue value={task.architecture} />],
              ['Health', <NumberValue value={task.health} />],
              ['Overall', <NumberValue value={task.overall} />],
            ]}
          />
          <SourceLink href={task.sourceLink} />
          {task.pullRequestUrl && <SourceLink href={task.pullRequestUrl} label="Pull request" />}
          <RawJson value={task.raw} />
        </>
      )}
    </Drawer>
  )
}
