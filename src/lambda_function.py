import boto3
import gzip 
import os 
import shutil

s3_client = boto3.client('s3')
cloudwatch = boto3.client('cloudwatch')


def handler(event, context):
    #Aqui guardamos detallitos de los archivos
    bucket_name = event['Records'][0]['s3']['bucket']['name']
    file_key = event['Records'][0]['s3']['object']['key']

    #Nadita de nada: en caso de que el archivo ya sea .gz, no hacer nadita
    if file_key.endswith('.gz'):
        print(f"[*] El archivo {file_key} ya esta comprimido.")
        return {'status': 'skipped', 'reason': 'already_compressed'}
    #Obtener el size original para el analisis de ahorro.
    response = s3_client.head_object(Bucket=bucket_name, Key=file_key)    
    original_size = response['ContentLength']

     # Si el archivo pesa menos de 10kb, no valdra la pena comprirlo, por lo cual nos ahorrariamos el gasto de CPU  
    if original_size <10240:
        print(f"[*] Archivo {file_key} muy chico. Omitiremos este archivo para ahorar CPU.")
        return {'status': 'skipped', 'reason': 'too_small'}


    download_path = f"/tmp/{os.path.basename(file_key)}"
    upload_path = f"{download_path}.gz"

    try: 
        #Pos aqui se descarga de forma temporal de Lambda
        print(f"[*] Descargando {file_key}...")
        s3_client.download_file(bucket_name, file_key, download_path)
        #Aqui se comprimen los archivos en .zg
        print(f"[*] Comrpimiendo {file_key}...")
        with open(download_path, 'rb') as f_in:
            with gzip.open(upload_path, 'wb') as f_out:
                 shutil.copyfileobj(f_in, f_out)

        #Subir el archivo comprimido a S3
        compressed_size = os.path.getsize(upload_path)
        savings = original_size - compressed_size
        
        s3_client.upload_file(upload_path, bucket_name, f"{file_key}.gz")
        s3_client.delete_object(Bucket=bucket_name, Key=file_key)

        # 2. ENVIAR MÉTRICA A CLOUDWATCH (El toque PRO)
        cloudwatch.put_metric_data(
            Namespace='EcoCompressMetrics',
            MetricData=[{
                'MetricName': 'BytesSaved',
                'Value': savings,
                'Unit': 'Bytes'
            }]
        )

        print(f"[+] Éxito. Ahorro: {savings} bytes.")
        return {'status': 'success', 'savings_bytes': savings}

    except Exception as e:
        print(f"[-] Error: {e}")
        raise e