import boto3
import subprocess
import time
from ..core.tools import log, handle_error

def deploy_to_aws(region: str = "us-west-2", instance_count: int = 5):
    """优化部署到 AWS ECS，支持自动缩放和错误处理"""
    try:
        # 构建 Docker 镜像
        subprocess.run(["docker", "build", "-t", "airdrop-tool", "."], check=True)
        
        # 推送镜像到 ECR
        ecr_client = boto3.client('ecr', region_name=region)
        repository = ecr_client.create_repository(repositoryName='airdrop-tool')['repository']['repositoryUri']
        subprocess.run(["docker", "tag", "airdrop-tool", repository], check=True)
        subprocess.run(["docker", "push", repository], check=True)

        # 创建 ECS 集群和服务
        ecs_client = boto3.client('ecs', region_name=region)
        ecs_client.create_cluster(clusterName='airdrop-cluster')
        
        # 配置任务定义
        task_definition = {
            'family': 'airdrop-task',
            'containerDefinitions': [{
                'name': 'airdrop-container',
                'image': repository,
                'memory': 512,
                'cpu': 256,
                'essential': True,
                'environment': [{'name': 'NUM_INSTANCES', 'value': str(instance_count)}]
            }]
        }
        ecs_client.register_task_definition(**task_definition)

        # 创建服务并启用自动缩放
        ecs_client.create_service(
            cluster='airdrop-cluster',
            serviceName='airdrop-service',
            taskDefinition='airdrop-task',
            desiredCount=instance_count,
            launchType='FARGATE',
            deploymentConfiguration={'minimumHealthyPercent': 50, 'maximumPercent': 200}
        )

        # 配置自动缩放策略
        autoscaling = boto3.client('application-autoscaling', region_name=region)
        autoscaling.register_scalable_target(
            ServiceNamespace='ecs',
            ResourceId='service/airdrop-cluster/airdrop-service',
            ScalableDimension='ecs:service:DesiredCount',
            MinCapacity=1,
            MaxCapacity=10
        )
        autoscaling.put_scaling_policy(
            PolicyName='AirdropScalePolicy',
            ServiceNamespace='ecs',
            ResourceId='service/airdrop-cluster/airdrop-service',
            ScalableDimension='ecs:service:DesiredCount',
            PolicyType='TargetTrackingScaling',
            TargetTrackingScalingPolicyConfiguration={
                'TargetValue': 70.0,  # 目标 CPU 利用率
                'PredefinedMetricSpecification': {
                    'PredefinedMetricType': 'ECSServiceUtilization'
                }
            }
        )
        log("AWS deployment completed successfully")
    except Exception as e:
        handle_error(e, "AWS deployment")

if __name__ == "__main__":
    deploy_to_aws()