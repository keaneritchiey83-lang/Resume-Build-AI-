output "cluster_name" {
  value = aws_eks_cluster.main.name
}

output "cluster_endpoint" {
  value     = aws_eks_cluster.main.endpoint
  sensitive = true
}

output "app_pod_role_arn" {
  value = aws_iam_role.app_pod.arn
}

output "cluster_autoscaler_role_arn" {
  value = aws_iam_role.cluster_autoscaler.arn
}

output "configure_kubectl" {
  value = "aws eks update-kubeconfig --region ${var.region} --name ${aws_eks_cluster.main.name}"
}
