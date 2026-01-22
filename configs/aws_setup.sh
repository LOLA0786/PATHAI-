#!/bin/bash
# Set up AWS Mumbai (ap-south-1) with DR in Singapore
aws configure set region ap-south-1

# VPC with private subnets (HIPAA-like)
aws ec2 create-vpc --cidr-block 10.0.0.0/16 --tag-specifications 'ResourceType=vpc,Tags=[{Key=Name,Value=PATHAI-VPC}]'
VPC_ID=None

# Private subnets
aws ec2 create-subnet --vpc-id  --cidr-block 10.0.1.0/24 --availability-zone ap-south-1a --tag-specifications 'ResourceType=subnet,Tags=[{Key=Name,Value=PATHAI-Private-A}]'
# Add more subnets...

# S3 bucket with encryption/lifecycle
aws s3api create-bucket --bucket pathai-vault --region ap-south-1 --create-bucket-configuration LocationConstraint=ap-south-1
aws s3api put-bucket-encryption --bucket pathai-vault --server-side-encryption-configuration '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'
aws s3api put-bucket-lifecycle-configuration --bucket pathai-vault --lifecycle-configuration file://lifecycle.json
cat <<JSON > lifecycle.json
{"Rules":[{"ID":"Glacier90","Status":"Enabled","Filter":{},"Transitions":[{"Days":90,"StorageClass":"GLACIER"}]}]}
JSON

# RDS Postgres (Multi-AZ)
aws rds create-db-instance --db-instance-identifier pathai-db --db-instance-class db.m5.large --engine postgres --engine-version 15.3 --multi-az --allocated-storage 100 --master-username admin --master-user-password securepass --db-name pathai

# ElastiCache Redis
aws elasticache create-cache-cluster --cache-cluster-id pathai-cache --cache-node-type cache.m5.large --engine redis --num-cache-nodes 2 --cache-subnet-group-name pathai-subnet-group  # Create subnet group first

# DR: Replication to ap-southeast-1 (Singapore)
aws rds create-db-instance-read-replica --db-instance-identifier pathai-db-dr --source-db-instance-identifier pathai-db --region ap-southeast-1 --db-instance-class db.m5.large
