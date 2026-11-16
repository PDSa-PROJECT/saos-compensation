# ADR 0002: Asynchronous model serving on AWS

- Date: 2026-11-16
- Status: Accepted; implementation and hardware validation pending

## Context

Develop reusable model-serving capability, starting with a larger Basal model and allowing later expansion to embeddings or regression models. The acquisition and extraction pipeline stays on the local machine; only model inference moves to AWS.

Initial usage consists of short batches followed by complete inactivity. Cold starts of several minutes are acceptable. Minimize idle compute costs, use On-Demand rather than Spot capacity, and create all AWS infrastructure through Terraform.

The current repository runs Basal in process, defaults to Remek/basal-2.0-4.5B and pins the engine to v2.4.1. Remote serving is not implemented. This decision does not change the existing runtime configuration or approve an engine upgrade.

## Decision

| Setting | Selected value |
|---|---|
| Service | Amazon SageMaker Asynchronous Inference |
| Region | `eu-north-1` (Stockholm) |
| Initial model | `Remek/basal-2.0-max` (11B) |
| Initial instance target | `ml.g6.xlarge`, one NVIDIA L4 GPU with 24 GB GPU memory |
| Purchase option | On-Demand, not Spot |
| Scaling | Minimum zero, maximum one instance |
| Initial invocation concurrency | One invocation per instance |
| Precision | Undecided; no implicit approval of quantization |
| Client | Local pipeline, using AWS-authenticated API calls |
| Request/result transport | S3 input objects and asynchronous output/failure objects |
| Provisioning | Terraform, including endpoint, model definition, IAM, ECR, S3 and scaling resources |

The 24 GB instance supersedes the previously discussed 32 GB candidate as the initial target. Instance type must be configurable so it can be changed later through Terraform. Changing instance type entails a managed endpoint update/redeployment and model reload, not necessarily an interruption-free resize. Do not automatically fall back to a more expensive instance or different precision.

Configure scale-up for queued work when capacity is zero, not only for a backlog exceeding a target value. Configure scale-down after work drains without repeatedly unloading the model between dependent requests. Exact scaling timings remain an implementation decision.

Use IAM authorization and HTTPS for endpoint access. The basic serving design does not require a custom public API gateway, an endpoint IP WHITELIST or a NAT gateway. This does not change the database IP WHITELIST in ADR 0001.

The serving approach should accommodate additional model deployments later without forcing them onto the same GPU, endpoint or model-specific request schema. The embedding model remains local initially; deployment of other models is not part of this decision.

## Request flow

1. The local pipeline uploads a model request to S3 and invokes the asynchronous endpoint with its location.
2. SageMaker queues the request and provisions capacity if needed.
3. A custom container loads Basal once and handles model calls, exposing SageMaker-compatible `/invocations` and `/ping` routes on port 8080.
4. SageMaker writes the response or failure output to S3.
5. The local pipeline retrieves the result and continues local extraction and validation.
6. Autoscaling releases GPU capacity after the batch drains and the scale-in conditions are met.

Extraction orchestration, source/leakage checks, records and checkpoints remain local. Introducing remote transport must not silently alter these contracts or repeat failed model operations without an explicit failure/recovery policy.

## Hardware validation conditions

The instance is a cost-first experiment target, not a confirmed fit:

- BF16 weights alone require approximately 22 GB, leaving little room on a 24 GB GPU for activations, runtime buffers and CUDA graphs.
- The Basal author's hardware documentation reports that basal-2.0-max-FP8 loaded on a 24 GB RTX 4090 but exhausted memory on a long prompt. This is not an L4 measurement, but demonstrates that smaller weight files alone do not establish fit.
- Published hardware results include newer engine versions and cannot be assumed to apply unchanged to the repository's pinned v2.4.1 engine.
- A general SageMaker hosting price listing does not establish Async-specific instance support or account quota in Stockholm; verify both before provisioning.
- Validate startup, the longest supported requests, actual peak GPU/host memory and the chosen runtime at concurrency one. Do not silently truncate inputs to make the model fit.

If validation fails, revisit precision, runtime or instance size with explicit approval. A paid AWS smoke test requires separate authorization. Precision and a larger instance have not been selected by this ADR.

## Cost estimate

The Stockholm SageMaker hosting price checked on 2026-11-16 for ml.g6.xlarge is $1.195 per instance-hour. Use this as a provisional rate, subject to Async support verification. Billing is for provisioned instance time, including startup and idle scale-down delay, not only time executing requests. Compute charges stop at zero instances; supporting storage and services can still be billed.

Illustrative compute costs assuming 15 minutes total startup/scale-down overhead per batch, not a measured duration:

| Processing per batch | Billed time | Compute per batch | 17–22 batches/month |
|---|---|---:|---:|
| 15 minutes | 30 minutes | $0.60 | $10–13 |
| 30 minutes | 45 minutes | $0.90 | $15–20 |
| 1 hour | 1 hour 15 minutes | $1.49 | $25–33 |
| 2 hours | 2 hours 15 minutes | $2.69 | $46–59 |

These estimates exclude tax, model/request/result storage, applicable S3 requests, ECR storage, endpoint volume storage, logs, scaling alarms and chargeable data transfer. Retention policies and actual artifact sizes remain to be specified. The database estimate in ADR 0001 is separate. No total deployment budget is validated until hardware fit and supporting costs are known.

## Alternatives considered

- **SageMaker Serverless Inference:** excluded for Basal 11B because it has no GPU support and at most 6 GB RAM. It may suit a smaller future model.
- **EC2 On-Demand GPU:** lower hourly compute prices, but requires managing serving, access and shutdown. Async was selected for managed queuing and scale-to-zero.
- **SageMaker real-time with inference components:** supports scale-to-zero, but requests fail during capacity startup and require explicit client recovery. Async queues work instead.
- **SageMaker Batch Transform:** releases compute after a job finishes, but requires prepared job inputs. Async better matches a local pipeline requesting model decisions as it progresses.
- **Spot GPU capacity:** discounted but interruptible; deferred in favor of a simpler initial On-Demand deployment.

## Remaining implementation decisions

- Verify Async instance support, regional quotas and capacity; validate the model/runtime memory fit.
- Pin the model revision and compatible engine/CUDA/PyTorch container versions; precision remains open.
- Define request/response validation, local transport integration and interruption recovery without duplicating completed inference.
- Define scaling thresholds, timeouts and bounded handling of cold starts and failures.
- Define least-privilege client/execution roles, S3 lifecycle rules, container/artifact publication and log retention without logging source payloads by default.
- Reuse the project's eventual Terraform state/authentication setup; do not provision infrastructure from application code or deployment SDK examples.

## References

- [SageMaker Async overview](https://docs.aws.amazon.com/sagemaker/latest/dg/async-inference.html)
- [Async scaling to and from zero](https://docs.aws.amazon.com/sagemaker/latest/dg/async-inference-autoscale.html)
- [Async limits, container compatibility and instance support](https://docs.aws.amazon.com/sagemaker/latest/dg/async-inference-troubleshooting.html)
- [SageMaker custom inference container contract](https://docs.aws.amazon.com/sagemaker/latest/dg/your-algorithms-inference-code.html)
- [Basal v2.8.1 hardware documentation](https://github.com/rkinas/basal/blob/v2.8.1/docs/HARDWARE.md)
- [Basal 2.0 Max model card](https://huggingface.co/Remek/basal-2.0-max)
- [Stockholm SageMaker price list](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonSageMaker/current/eu-north-1/index.json)
