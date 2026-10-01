import { lazy, type ComponentType } from 'react'

const OverviewPage = lazy(() =>
  import('../pages/overview/OverviewPage').then((module) => ({ default: module.OverviewPage })),
)
const DatasetPage = lazy(() =>
  import('../pages/dataset/DatasetPage').then((module) => ({ default: module.DatasetPage })),
)
const ResultsPage = lazy(() =>
  import('../pages/results/ResultsPage').then((module) => ({ default: module.ResultsPage })),
)
const TasksPage = lazy(() =>
  import('../pages/tasks/TasksPage').then((module) => ({ default: module.TasksPage })),
)
const QualityPage = lazy(() =>
  import('../pages/quality/QualityPage').then((module) => ({ default: module.QualityPage })),
)
const StatisticsPage = lazy(() =>
  import('../pages/statistics/StatisticsPage').then((module) => ({
    default: module.StatisticsPage,
  })),
)
const TokensPage = lazy(() =>
  import('../pages/tokens/TokensPage').then((module) => ({ default: module.TokensPage })),
)
const PromptsPage = lazy(() =>
  import('../pages/prompts/PromptsPage').then((module) => ({ default: module.PromptsPage })),
)
const LeaderboardPage = lazy(() =>
  import('../pages/leaderboard/LeaderboardPage').then((module) => ({
    default: module.LeaderboardPage,
  })),
)
const SubmitPage = lazy(() =>
  import('../pages/submit/SubmitPage').then((module) => ({ default: module.SubmitPage })),
)
const DownloadsPage = lazy(() =>
  import('../pages/downloads/DownloadsPage').then((module) => ({ default: module.DownloadsPage })),
)

export const routes: Record<string, ComponentType> = {
  '/': OverviewPage,
  '/dataset': DatasetPage,
  '/results': ResultsPage,
  '/tasks': TasksPage,
  '/quality': QualityPage,
  '/statistics': StatisticsPage,
  '/tokens': TokensPage,
  '/prompts': PromptsPage,
  '/leaderboard': LeaderboardPage,
  '/submit': SubmitPage,
  '/downloads': DownloadsPage,
}

export function readRoute(): string {
  const path = (window.location.hash.slice(1).split('?')[0] || '/').replace(/\/$/, '') || '/'
  return routes[path] ? path : '/'
}
