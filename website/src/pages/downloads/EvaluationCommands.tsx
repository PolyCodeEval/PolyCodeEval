import { useState } from 'react'
import { Check, Copy } from 'lucide-react'

const commands = [
  [
    'L0',
    'python scripts/run_l0_eval.py --all --solver precomputed:<generated-output> --output <evaluation-output>',
  ],
  [
    'L1',
    'python scripts/run_l1_eval.py --all --solver precomputed:<generated-output> --output <evaluation-output>',
  ],
  [
    'L2',
    'python scripts/run_l2_eval.py --all --solver precomputed:<generated-output> --tests both --output <evaluation-output>',
  ],
  [
    'L3',
    'python scripts/run_l3_eval.py --all --solver precomputed:<generated-output> --tests both --output <evaluation-output>',
  ],
]

export function EvaluationCommands() {
  const [copied, setCopied] = useState('')
  const copy = async (level: string, command: string) => {
    await navigator.clipboard.writeText(command)
    setCopied(level)
    window.setTimeout(() => setCopied(''), 1200)
  }
  return (
    <div className="evaluation-commands">
      {commands.map(([level, command]) => (
        <div key={level}>
          <span className={`level-swatch level-${level.toLowerCase()}`}>{level}</span>
          <code>{command}</code>
          <button
            className="icon-button"
            title={`Copy ${level} command`}
            onClick={() => copy(level, command)}
          >
            {copied === level ? <Check size={15} /> : <Copy size={15} />}
          </button>
        </div>
      ))}
    </div>
  )
}
