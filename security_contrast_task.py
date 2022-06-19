# -*- coding: utf-8 -*-
"""security_contrast_task.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1Fk61DXDPLYCaqHz8RM8zmEfITRqvp4xl
"""

!pip install boto3
!pip install --upgrade botocore==1.23.26
!pip install --upgrade urllib3==1.22.0
!sudo pip install awscli --ignore-installed six
!aws configure set region us-east-1

# -*- coding: utf-8 -*-

import json
from io import BytesIO
import boto3
from zipfile import ZipFile
import urllib3

class ActionsConverter:
# Example of method calls and their permissions
    actions_to_permissions = {
        "s3_client.get_object": ["s3:GetObject"],
        "sqs_client.send_message_batch": ["sqs:SendMessage"],
        "sqs_client.create_queue": ["sqs:CreateQueue", "sqs:TagQueue"],
        "dynamodb_client.delete_item": ["dynamodb:DeleteItem"],
        "dynamodb_client.describe_table":["dynamodb:DescribeTable"],
        "dynamodb_client.transact_get_items":["dynamodb:TransactGetItems"],
        "dynamodb_client.put_item":["dynamodb:PutItem"]
        }
    def __init__(self) -> None:
        self.actions = self.actions_to_permissions.keys()
    def find_actions(self, input: str) -> list:
        found_actions = []
        for action in self.actions:
            if action in input:
                print("Found action", action, "in input str")
                found_actions.append(action)
        return found_actions       
"""
input : 
    - lambda code (str)
    - lambda policies (array of policies, each policy expressed by json object)
output :
    - return a least privilige policy based on the actions used in lambda code as json object
"""      
def create_LPP( lambda_code , lambda_policies):
    actions_converter = ActionsConverter()
    lambda_actions = actions_converter.find_actions(lambda_code)
    policy_actions=[]
    for action in lambda_actions:
        policy_actions.append( "".join(actions_converter.actions_to_permissions[action]) )
    updated_policies = set()
    resources = set()
    updated_policies.update(policy_actions)
    for policy in lambda_policies:
        policy = json.loads(policy)
        for sid in policy["Statement"]:
            if( isinstance(sid["Action"], str) ): #sid["Action"] should be str or list object
                permissions = [ sid["Action"] ]
            elif( isinstance(sid["Action"], list) ):
                permissions = sid["Action"].copy() 
            copy_permissions=permissions.copy()
            for action in copy_permissions: #remove unneeded permssions from each statment permissions 
                if str(action) not in policy_actions:
                        permissions.remove(str(action))
            if permissions != [] : #(not empty) there are needed permissions in the policy
                if len(permissions) == 1:
                    sid["Action"] = ''.join(permissions)
                else:
                    sid["Action"] = permissions
                updated_policies.add(sid["Action"])
                resources.update(sid["Resource"])
    
    recommended_policy = {
          'Version': "2012-10-17",
          'Statement': [
              {
                  "Effect": "Allow",
                  "Action": list(updated_policies),
                  "Resource": list(resources)
              }
          ]
      }
    print(updated_policies)
    return json.dumps(recommended_policy)

"""
input : 
    - url of lambda function (str)
output :
    - download the zipped file from url, unzipped it and return the lambda code (str)  
""" 
def download_and_unzip_lambda(function_url):
    http = urllib3.PoolManager()
    responsed_zipfile = http.request( "GET" , function_url )
    function_zipf = ZipFile( BytesIO( responsed_zipfile.data ) )
    function_zipf.extractall(path='.')
    with open(r"lambda_function.py", "r") as f:
        lambda_code = f.read()
    f.close()
    return lambda_code

"""
input : 
    - lambda name (str)
output :
    - gets the lambda code and policies and use it to return a least privilige policy (json) 
"""   
def create_LPP_from_lambda_name(lambda_name):
    aws_access_key_id=""
    aws_secret_access_key=""
    aws_session_token=""
    client = boto3.client("lambda",region_name="us-east-1",
                          aws_access_key_id=aws_access_key_id,
                          aws_secret_access_key=aws_secret_access_key,
                          aws_session_token=aws_session_token)
    responsed_function_info = client.get_function(FunctionName=lambda_name)
    function_url = responsed_function_info["Code"]["Location"]
    lambda_code = download_and_unzip_lambda(function_url)#get the lambda function, dowonload and extract it.
    role_name = responsed_function_info['Configuration']['Role'].split('/')[2]
    iam = boto3.client("iam",region_name="us-east-1",
                          aws_access_key_id=aws_access_key_id,
                          aws_secret_access_key=aws_secret_access_key,
                          aws_session_token=aws_session_token)
    lambda_role_policy_names = iam.list_role_policies(RoleName=role_name)["PolicyNames"]
    lambda_role_policies = []
    for policy_name in lambda_role_policy_names:
        lambda_role_policies.append(json.dumps(iam.get_role_policy(RoleName=role_name,PolicyName=policy_name)['PolicyDocument']))
    return create_LPP( lambda_code , lambda_role_policies )
    
print("exampl:",create_LPP_from_lambda_name("sample_s3_dynamodb"))

