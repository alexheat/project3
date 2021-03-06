#!/usr/bin/env python
"""Extract events from kafka and write them to hdfs
"""
import json
from pyspark.sql import SparkSession, Row
from pyspark.sql.functions import udf, from_json
from pyspark.sql.types import StructType, StructField, StringType, DoubleType
from pyspark import SparkContext
import sys

def purchase_or_sell_event_schema():

    return StructType([
        StructField( "event_type", StringType(), True),
        StructField( "item", StringType(), True),
        StructField( "item_type", StringType(), True),
        StructField( "user_id", StringType(), True),
        StructField( "price", DoubleType(), True),
        StructField( "currency", StringType(), True),

    ])

@udf('boolean')
def is_purchase(event_string):
    event = json.loads(event_string)
    return event['event_type'] == 'purchase_item'
    
@udf('boolean')
def is_sell(event):
    event = json.loads(event)
    return event['event_type'] == 'sell_item'


sc =SparkContext()

def main():
    """main
    """
    spark = SparkSession \
        .builder \
        .appName("ExtractEventsJob") \
        .getOrCreate()
    
    #Read events from kafka
    game_api_raw = spark \
      .readStream \
      .format("kafka") \
      .option("kafka.bootstrap.servers", "kafka:29092") \
      .option("subscribe","events") \
      .load() 
    
    sells = game_api_raw \
        .filter(is_sell(game_api_raw.value.cast("string"))) \
        .select(game_api_raw.value.cast("string").alias("game_api_raw"),
                    game_api_raw.timestamp.cast("string"),
                    from_json(game_api_raw.value.cast("string"),
                                purchase_or_sell_event_schema()).alias("json")) \
        .select("game_api_raw", "timestamp", "json.*")

    
    purchases = game_api_raw \
        .filter(is_purchase(game_api_raw.value.cast("string"))) \
        .select(game_api_raw.value.cast("string").alias("game_api_raw"),
                    game_api_raw.timestamp.cast("string"),
                    from_json(game_api_raw.value.cast("string"),
                                purchase_or_sell_event_schema()).alias("json")) \
        .select("game_api_raw", "timestamp", "json.*")
    
    sell_sink = sells \
        .writeStream \
        .format("parquet") \
        .option("checkpointLocation", "/tmp/checkpoints_for_sells") \
        .option("path", "/tmp/game/sell_api") \
        .trigger( processingTime="10 seconds") \
        .outputMode("append") \
        .start ()
   
    purchase_sink = purchases \
        .writeStream \
        .format("parquet") \
        .option("checkpointLocation", "/tmp/checkpoints_for_purchases") \
        .option("path", "/tmp/game/purchase_api") \
        .trigger( processingTime="10 seconds") \
        .outputMode("append") \
        .start ()
    
    game_api_raw_sink = game_api_raw \
        .writeStream \
        .format("parquet") \
        .option("checkpointLocation", "/tmp/checkpoints_for_game_api_raw") \
        .option("path", "/tmp/game/all_api_requests_raw") \
        .trigger( processingTime="10 seconds") \
        .outputMode("append") \
        .start ()
    
    sell_sink.awaitTermination()
    
if __name__ == "__main__":
    main()