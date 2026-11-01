resource "aws_launch_template" "confidential" {
  count       = var.confidential_node_group_enabled ? 1 : 0
  name_prefix = "${local.name}-confidential-"

  enclave_options {
    enabled = true
  }

  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
  }

  tag_specifications {
    resource_type = "instance"
    tags = {
      Name = "${local.name}-confidential"
    }
  }
}

resource "aws_eks_node_group" "confidential" {
  count           = var.confidential_node_group_enabled ? 1 : 0
  cluster_name    = aws_eks_cluster.main.name
  node_group_name = "confidential"
  node_role_arn   = aws_iam_role.node.arn
  subnet_ids      = var.private_subnet_ids
  instance_types  = var.confidential_node_instance_types
  capacity_type   = "ON_DEMAND"

  launch_template {
    id      = aws_launch_template.confidential[0].id
    version = aws_launch_template.confidential[0].latest_version
  }

  scaling_config {
    min_size     = var.confidential_node_min_size
    desired_size = var.confidential_node_min_size
    max_size     = var.confidential_node_max_size
  }

  labels = {
    "career.ai/node-pool"            = "confidential"
    "career.ai/confidential-compute" = "true"
  }

  taint {
    key    = "career.ai/confidential"
    value  = "true"
    effect = "NO_SCHEDULE"
  }

  depends_on = [
    aws_iam_role_policy_attachment.node_worker,
    aws_iam_role_policy_attachment.node_ecr,
  ]

  lifecycle {
    ignore_changes = [scaling_config[0].desired_size]
  }
}
