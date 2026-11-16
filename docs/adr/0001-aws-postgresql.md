# ADR 0001: Managed PostgreSQL for student experiments on AWS

- Date: 2026-11-16
- Status: Accepted; implementation pending

## Context

The project needs PostgreSQL with JSONB and pgvector for judgment data, extracted features, targets and embeddings. Database ingestion is not implemented yet. Initial usage is a small student project, approximately 2–3 hours per session, 4–5 times a week (roughly 35–65 active hours per month). Dataset size is not yet known.

The database must be managed, preserve data between experiments and support access from a Mac and potentially a university cluster. Continuous availability is not required. Minimize ongoing cost and create all project AWS infrastructure through Terraform.

## Decision

| Setting | Selected value |
|---|---|
| Service | Amazon RDS for PostgreSQL, with pgvector |
| Region | `eu-north-1` (Stockholm) |
| Instance | `db.t4g.micro`: 2 burstable vCPUs, 1 GiB RAM |
| Availability | Single-AZ; no read replicas |
| Storage | 20 GB gp3 |
| Network | Dedicated project VPC, not the default VPC |
| Subnets | Public subnets in two availability zones, with an internet gateway |
| NAT gateway | None |
| Endpoint | Publicly accessible |
| Ingress | TCP 5432 restricted to an explicit IP WHITELIST in Terraform |
| Transport | Require TLS |
| Master credentials | RDS-managed password in AWS Secrets Manager; Terraform must not read the password into state |
| Automated backups | Disabled (`backup_retention_period = 0`) |
| Deletion protection | Enabled |
| Start | Manual, when needed |
| Stop | Automatic every day at 02:00, timezone `Europe/Warsaw` |
| Scheduling | EventBridge Scheduler calling the RDS stop API directly, with Terraform-managed permissions; no Lambda |

The DB subnet group spans two availability zones because RDS requires this even for a Single-AZ instance. It does not imply a second database instance.

The IP WHITELIST must contain actual public outbound addresses, not local Wi-Fi addresses. A single IPv4 address uses `/32`; university network ranges require verification. Do not allow `0.0.0.0/0`. If a client address changes, update the WHITELIST through Terraform.

Expose the instance class as a Terraform input so it can be changed later. Resizing normally modifies the existing instance without a manual data migration, but causes downtime. Model inference runs separately; this database does not host Basal or the embedding model.

## Alternatives considered

- **Aurora PostgreSQL Serverless v2:** supports pgvector and automatic pause/resume with zero compute capacity while paused. It avoids explicit start/stop, but active capacity costs more than a small RDS instance. Open client connections prevent auto-pause. RDS was selected for the lowest expected cost with explicit stopping.
- **Self-managed PostgreSQL on EC2:** rejected because a managed database is required.
- **Private RDS with a tunnel or VPN:** adds access infrastructure and operational complexity for external clients. A restricted public endpoint was selected instead.
- **Default VPC:** less setup, but depends on shared, pre-existing networking. A dedicated VPC provides isolation and Terraform reproducibility without a VPC, subnet or internet-gateway hourly fee.

## Cost estimate

Indicative on-demand prices checked for Stockholm on 2026-11-16, before tax and credits:

| Component | Assumption | Monthly USD |
|---|---|---:|
| RDS compute | 35–65 hours at $0.016/hour | $0.56–$1.04 |
| gp3 storage | 20 GB at $0.12/GB-month | $2.40 |
| Public IPv4 | One address allocated for 730 hours at $0.005/hour | $3.65 |
| Secrets Manager | One secret, approximately $0.40/month | $0.40 |
| **Estimated total** | Stopped between sessions | **$7.01–$7.49** |

Storage and public IPv4 remain billed while RDS is stopped. At 730 running hours, the same estimate becomes approximately $18.13/month including the secret. Start/stop transitions and automatic restarts can increase billed compute beyond experiment hours.

These are not a spending cap. They exclude surplus burstable CPU credits, secret API calls, chargeable data transfer, optional monitoring and additional backup/snapshot storage. Scheduler usage is expected to fit its free-tier allowance. Verify current pricing and any additional resources before applying Terraform.

For comparison, Aurora Standard at an average 0.5–1 ACU during 35–65 active hours was estimated at $7.41–$14.06/month before the secret, assuming 10 GB storage, one million storage I/O requests and one public IPv4. This is illustrative, not a performance-equivalent comparison or a measured capacity requirement.

## Consequences and limitations

- RDS automatically starts after seven consecutive days stopped. The nightly stop is a safety net, not a guarantee of zero compute billing during extended absence: the database can run until the next 02:00 schedule.
- Starting RDS can take several minutes or longer. The nightly stop can interrupt work; it is not idle detection.
- Scheduled stop execution must handle already-stopped instances without unnecessary retries; exact failure handling remains to be designed.
- No automated backups means no automated restore points or point-in-time recovery. Deletion protection does not protect against SQL mistakes or data corruption.
- One GiB RAM is a starting point, not a validated sizing result. Vector index creation, larger queries and concurrent clients may require resizing.
- Public access still requires both an allowed source address and valid database authentication. TLS must be enforced and verified by clients.

## Remaining implementation decisions

- PostgreSQL and pgvector versions, extension installation and schema migrations.
- Actual IP WHITELIST entries for the Mac and university cluster.
- Terraform state storage, provider/version pinning and deployment authentication.
- Application database roles and secret access permissions.
- Manual start interface, scheduler failure handling and final-snapshot policy on deletion.
- Database ingestion and application integration, separate from infrastructure provisioning.
- Model-serving architecture, which is outside this ADR.

## References

- [AWS Stockholm RDS price list](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonRDS/current/eu-north-1/index.json)
- [RDS stop/start behavior and retained public IPv4](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_StopInstance.html)
- [Aurora Serverless v2 automatic pause/resume](https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/aurora-serverless-v2-auto-pause.html)
