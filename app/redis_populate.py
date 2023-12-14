import redis
import pandas as pd

def populate_redis_cache(csv_file_path, redis_host, redis_port):
    try:
        df = pd.read_csv(csv_file_path)
        redis_client = redis.StrictRedis(host=redis_host, port=redis_port, db=0)

        # Iterate through each row in the DataFrame and populate the cache
        for index, row in df.iterrows():
            venue_id = row['venue_id']
            avg_preparation_time = row['avg_preparation_time']

            # Store the data in the Redis cache with a specific key format
            cache_key = f"venue:{venue_id}:avg_preparation_time"
            redis_client.set(cache_key, avg_preparation_time)

        return True, "Cache population successful"
    except Exception as e:
        return False, f"Cache population failed: {str(e)}"


if __name__=='__main__':
    # Usage example:
    csv_file_path = 'venue_preparation_sample.csv'
    redis_host = 'redis'    # Replace with your Redis server's hostname or IP address
    redis_port = 6379           # Replace with your Redis server's port

    success, message = populate_redis_cache('venue_preparation.csv', redis_host, redis_port)

    if success:
        print(message)
    else:
        print(f"Error: {message}")

    redis_client = redis.StrictRedis(host=redis_host, port=redis_port, db=0)

    # List all keys in the Redis database
    all_keys = redis_client.keys('*')

    for key in all_keys:
        print(key.decode('utf-8'))

    print('done')
