data "aws_caller_identity" "current" {}

data "aws_partition" "current" {}

resource "aws_scheduler_schedule_group" "this" {
  name = "${var.name_prefix}-database"
}

resource "aws_iam_role" "scheduler" {
  name = "${var.name_prefix}-rds-stop"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Action    = "sts:AssumeRole"
      Principal = { Service = "scheduler.amazonaws.com" }
      Condition = {
        StringEquals = { "aws:SourceAccount" = data.aws_caller_identity.current.account_id }
        ArnEquals    = { "aws:SourceArn" = aws_scheduler_schedule_group.this.arn }
      }
    }]
  })
}

resource "aws_iam_role_policy" "scheduler" {
  name = "stop-project-database"
  role = aws_iam_role.scheduler.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = "rds:StopDBInstance"
      Resource = aws_db_instance.this.arn
    }]
  })
}

resource "aws_scheduler_schedule" "stop" {
  name                         = "${var.name_prefix}-rds-stop"
  group_name                   = aws_scheduler_schedule_group.this.name
  description                  = "Nightly stop of the experiment database; starting remains manual."
  schedule_expression          = var.stop_schedule.expression
  schedule_expression_timezone = var.stop_schedule.timezone
  state                        = var.stop_schedule.enabled ? "ENABLED" : "DISABLED"

  flexible_time_window {
    mode = "OFF"
  }

  target {
    arn      = "arn:${data.aws_partition.current.partition}:scheduler:::aws-sdk:rds:stopDBInstance"
    role_arn = aws_iam_role.scheduler.arn
    input    = jsonencode({ DBInstanceIdentifier = aws_db_instance.this.identifier })

    retry_policy {
      maximum_event_age_in_seconds = 3600
      maximum_retry_attempts       = 0
    }
  }

  depends_on = [aws_iam_role_policy.scheduler]
}
