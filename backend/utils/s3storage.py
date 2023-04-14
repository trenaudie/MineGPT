from redirect_stdout import redirect_stdout_to_logger
from config import Config
import boto3
from botocore.exceptions import ClientError
import os
from logger import logger
import sys
sys.path.append('/Users/tanguyrenaudie/Documents/TanguyML/MineGPT/backend')


# Create a new session using the access key and secret access key of the new user
session = boto3.Session(aws_access_key_id=Config.AWS_ACCESS_KEY_ID,
                        aws_secret_access_key=Config.AWS_SECRET_ACCESS_KEY)
bucket_name = 'minefiles'


def delete_file_from_s3(file_key, bucket_name, session):
    # Create an S3 client
    s3_client = session.client('s3')

    # Delete the file from the S3 bucket
    try:
        s3_client.delete_object(Bucket=bucket_name, Key=file_key)
        print(f"Deleted file {file_key} from bucket {bucket_name}")
    except ClientError as e:
        print(f"Error deleting file {file_key} from bucket {bucket_name}: {e}")
        return False
    return True


def upload_file(file_path, file_name, bucket, session: boto3.Session, object_name=None):
    """Upload a file to an S3 bucket

    :param file_name: File to upload
    :param bucket: Bucket to upload to
    :param object_name: S3 object name. If not specified then file_name is used
    :return: True if file was uploaded, else False
    """

    # If S3 object_name was not specified, use file_name
    if object_name is None:
        object_name = os.path.basename(file_name)

    # Upload the file
    s3_client = session.client('s3')
    try:
        # print working directory
        print(os.getcwd())
        response = s3_client.upload_file(file_path, bucket, object_name)
    except ClientError as e:
        logger.error(e)
        return False
    return True


def upload_Admin(folder, bucket_name, session):
    for root, dirs, files in os.walk(folder):
        for filename in files:
            item_path = os.path.join(root, filename)
            if os.path.isfile(item_path):
                # Get the relative path from the root folder
                rel_path = os.path.relpath(item_path, folder)
                # Replace path separators with underscores
                new_filename = rel_path.replace(os.path.sep, '_')
                print(filename)
                # Upload the file
                upload_file(item_path, new_filename, bucket_name, session)


if __name__ == "__main__":
    with redirect_stdout_to_logger(logger):
        # Create an IAM client
        iam = session.client('iam')

        # Call the get_user() method to get information about the current user
        user = iam.get_user()

        # Print the user's username
        print('Current user:', user['User'])
        print('current region ', session.region_name)

        # Get the policies attached to the user
        attached_policies = iam.list_attached_user_policies(
            UserName=user['User']['UserName'])

        # Get the inline policies attached to the user
        inline_policies = iam.list_user_policies(
            UserName=user['User']['UserName'])

        all_policies = iam
        # Print the policy ARNs
        for policy in attached_policies['AttachedPolicies']:
            print(policy['PolicyArn'])

        for policy in inline_policies['PolicyNames']:
            policy_document = iam.get_user_policy(
                UserName=user['User']['UserName'], PolicyName=policy)
            print(policy_document['PolicyArn'])
        # upload_file('backend/temp/Probabilite1.pdf', bucket_name)

            # Get the groups the user belongs to
        groups = iam.list_groups_for_user(UserName=user['User']['UserName'])

        # Print the group names
        for group in groups['Groups']:
            print(group['GroupName'])

        response = iam.list_attached_group_policies(
            GroupName='mineGPTgroup',
        )
        print("group policies ", response)

        upload_Admin('backend/database/1A', bucket_name, session)
        delete_file_from_s3('Probabilité II.pdf', bucket_name, session)
