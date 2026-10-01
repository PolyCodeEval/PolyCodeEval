import { Braces, Coffee, FileCode2, Gem, Terminal } from 'lucide-react'
import type { DatasetDownload } from './downloads.types'

export const datasets: DatasetDownload[] = [
  {
    id: 'python',
    label: 'Python',
    repositories: 13,
    image: 'err404notfound/polycodeeval-datasets-python',
    icon: Gem,
  },
  {
    id: 'javascript',
    label: 'JavaScript',
    repositories: 11,
    image: 'err404notfound/polycodeeval-datasets-javascript',
    icon: Braces,
  },
  {
    id: 'java',
    label: 'Java',
    repositories: 11,
    image: 'err404notfound/polycodeeval-datasets-java',
    icon: Coffee,
  },
  {
    id: 'go',
    label: 'Go',
    repositories: 12,
    image: 'err404notfound/polycodeeval-datasets-go',
    icon: Terminal,
  },
  {
    id: 'cpp',
    label: 'C++',
    repositories: 11,
    image: 'err404notfound/polycodeeval-datasets-cpp',
    icon: FileCode2,
  },
]

export const taskCounts = { L0: 58, L1: 58, L2: 150, L3: 2324 }
