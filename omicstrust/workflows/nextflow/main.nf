#!/usr/bin/env nextflow

params.input = null
params.output = "results/nextflow_audit"
params.batch_key = "batch"
params.label_key = "signal_label"

process audit {
  input:
  path input_file

  output:
  path params.output

  script:
  """
  omicstrust audit ${input_file} --batch-key ${params.batch_key} --label-key ${params.label_key} --output ${params.output}
  """
}

workflow {
  audit(file(params.input))
}
