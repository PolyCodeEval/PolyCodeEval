import {
  BookOpen,
  CheckCircle2,
  Code2,
  Database,
  Download,
  FileCode2,
  Layers3,
  Play,
  Sigma,
  Trophy,
  Upload,
  type LucideIcon,
} from 'lucide-react'

export interface NavigationItem {
  path: string
  title: string
  icon: LucideIcon
  group: 'Benchmark' | 'Community'
}

export const navigationItems: NavigationItem[] = [
  { path: '/', title: 'Overview', icon: Database, group: 'Benchmark' },
  { path: '/dataset', title: 'Dataset Explorer', icon: Layers3, group: 'Benchmark' },
  { path: '/results', title: 'Results Explorer', icon: CheckCircle2, group: 'Benchmark' },
  { path: '/tasks', title: 'Task Explorer', icon: FileCode2, group: 'Benchmark' },
  { path: '/quality', title: 'Quality & Coverage', icon: BookOpen, group: 'Benchmark' },
  { path: '/statistics', title: 'Statistical Analysis', icon: Sigma, group: 'Benchmark' },
  { path: '/tokens', title: 'Token & Cost', icon: Code2, group: 'Benchmark' },
  { path: '/prompts', title: 'Prompts & Reproduction', icon: Play, group: 'Benchmark' },
  { path: '/leaderboard', title: 'Leaderboard', icon: Trophy, group: 'Community' },
  { path: '/submit', title: 'Submit', icon: Upload, group: 'Community' },
  { path: '/downloads', title: 'Downloads', icon: Download, group: 'Community' },
]
