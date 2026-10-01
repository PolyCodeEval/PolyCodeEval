import { Download, FileArchive, FileJson2 } from 'lucide-react'

const resources = [
  {
    title: 'Submission metadata template',
    detail: 'The only additional JSON file required for a result submission',
    path: 'data/submit/submission-template.json',
    icon: FileJson2,
  },
  {
    title: 'Submission JSON Schema',
    detail: 'Machine-readable schema version 2',
    path: 'data/submit/submission-schema.json',
    icon: FileJson2,
  },
  {
    title: 'Result Submission Kit',
    detail: 'Template metadata, native directory example, and packaging instructions',
    path: 'data/submit/result-submission-kit.zip',
    icon: FileArchive,
  },
]

export function ResultSubmissionKit() {
  return (
    <div className="template-list">
      {resources.map((resource) => (
        <div className="template-row submission-resource" key={resource.path}>
          <span className="resource-icon">
            <resource.icon size={17} />
          </span>
          <div>
            <strong>{resource.title}</strong>
            <span>{resource.detail}</span>
          </div>
          <a
            className="button button-quiet"
            href={`${import.meta.env.BASE_URL}${resource.path}`}
            download
          >
            <Download size={15} /> Download
          </a>
        </div>
      ))}
    </div>
  )
}
