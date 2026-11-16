# Terraform infrastructure

One root stack composes provider-specific modules. Currently implemented: AWS VPC and RDS. SageMaker will be added separately under `modules/aws/sage_maker`.

```text
infrastructure/terraform/       # root stack, backend, providers and inputs
  modules/aws/vpc/              # dedicated VPC and two public subnets
  modules/aws/rds/              # PostgreSQL, TLS, IP WHITELIST and managed credentials
```

Keep provider credentials and configuration in the root stack, not child modules. Future GCP modules can live under `modules/gcp/` with their provider configured at the root; no GCP provider is installed until used. Backend storage is independent of deployment providers.

## State and credentials

The existing S3 bucket `saos-infra-tf-state-bucket-549048581262-eu-north-1-an` in `eu-north-1` stores state at `saos-compensation/terraform.tfstate`. Terraform does not create or manage this bucket. S3-native locking is enabled; no DynamoDB table is required.

The bucket must already exist. Verify encryption, restricted access and versioning on the existing bucket before first use. The operator needs state-object read/write access and lock-object read/write/delete access, plus appropriate bucket listing and any required KMS permissions. Never grant broad public access to the state bucket.

Use the standard AWS credential chain, preferably a short-lived AWS profile/SSO session. Do not put credentials in Terraform files, backend configuration or variable files. Local variable files, state, saved `.tfplan` files and `.terraform/` are ignored; commit `.terraform.lock.hcl` for reproducible provider installation.

## Local checks

Requires Terraform >= 1.10 and < 2.0. Run from this directory:

```bash
terraform fmt -check -recursive
terraform init -backend=false
terraform validate
```

For deployment, copy `terraform.tfvars.example` to `terraform.tfvars`, review values, authenticate to AWS and initialize the real backend with `terraform init`. Planning contacts AWS; applying provisions resources and requires explicit approval. No apply is part of initial setup.

## Network

The VPC uses DNS support and hostnames, two public subnets in separate available standard availability zones, one internet gateway and a shared public route table. There is no NAT gateway, VPN, bastion or load balancer. Public routing does not authorize inbound access; RDS has its own security group and IP WHITELIST.

Subnet public-IP auto-assignment is disabled; individual resources must explicitly request public access. The default VPC CIDR is `10.42.0.0/16`; `public_subnet_newbits = 8` derives `10.42.0.0/24` and `10.42.1.0/24`.

Architecture decisions: [database](../../docs/adr/0001-aws-postgresql.md), [model serving](../../docs/adr/0002-asynchronous-model-serving.md).

## PostgreSQL

Defaults: PostgreSQL 17, Single-AZ `db.t4g.micro`, encrypted 20 GiB gp3, no storage autoscaling, no automated backups, deletion protection, public endpoint and enforced TLS. Set `rds_ip_whitelist` to actual client public IPv4 CIDRs before connecting; empty means no client ingress, and /0 is rejected.

RDS manages the master password in Secrets Manager; Terraform outputs only its ARN. Client identities need separately scoped permission to retrieve it. Use the RDS CA certificate bundle and `sslmode=verify-full` when connecting, not encryption without certificate verification. PostgreSQL minor-version upgrades are automatic; resize/settings changes normally wait for the maintenance window because `apply_immediately` is false.

The PostgreSQL engine supports pgvector, but enabling it and managing application schemas are database migrations, not network provisioning. After connecting, an authorized database administrator can run `CREATE EXTENSION IF NOT EXISTS vector;`. No SQL provider or password retrieval is embedded in Terraform.

Final snapshots are also disabled by default. To keep a final snapshot, set `rds.skip_final_snapshot = false` and provide a unique `rds.final_snapshot_identifier`. Deletion first requires explicitly disabling `rds.deletion_protection`. Neither deletion protection nor disabled automated backups provides recovery from SQL mistakes.
