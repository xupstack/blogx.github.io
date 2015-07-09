Title: 用Spark Streaming搭建Lambda架构
Slug: building-lambda-architecture-with-spark-streaming
Date: 2015-07-01
Category: Spark
Author: 杨文华
Tags: Spark Streaming, Lambda Architecture
Type: 翻译
OriginAuthor: Gwen Shapira (@gwenshap)
OriginTime: 2014-08-29
OriginUrl: http://blog.cloudera.com/blog/2014/08/building-lambda-architecture-with-spark-streaming/


**Apache Spark在批处理/ETL和流式处理方面的广泛应用，让Lambda架构成为可能。**

几件事让你将注意力集中在从一个临时需求，到一个核心项目上。

记得有一次，在跟一个客户历经了三周时间，设计实现了一个POC（proof-of-concept，概念验证）数据摄取管道之后，客户的架构主管告诉我们：

*你知道吗，我很喜欢这个设计 - 我喜欢数据在到达时已经经过验证；我喜欢设计里面，将原始数据存储起来做研究分析，同时又做了一层汇总预处理，以快速响应业务分析师的需求；我还喜欢自动处理数据延迟，以及自动处理数据结构和算法变化的机制。*

*但是，他继续说，我真的希望有一个实时处理模块。从数据被收集，到数据报表展现有一个小时的时延。我知道这样做可以提高效率，同时也让我们能够对数据做清洗。但是在我们的部分应用场景中，能够立马对新的数据做出反应，比保证数据100%经过验证更为重要。*

*我们能快速的在POC中增加一个实时数据处理模块吗？它可以让我们的用户更加满意。*

这个架构师客户所提到的正是我们所说的[Lambda架构](http://lambda-architecture.net/) - 最早由Nathan Marz提出，该架构通常包含批处理和实时处理两个部分。人们经常同时需要这两部分（译注：而不仅仅是实时部分），原因是实时的数据天生存在一个问题：不能百分百保证每条数据发送/接收了一次，存在一些重复发送/接收的数据，会产生噪音。数据因为网络或者服务器不稳定造成的延迟，也常常会导致一些问题。Lambda架构通过处理两次数据来处理这些问题：一次是数据实时处理，另一次是数据批量处理 - 实时处理保证快速，而批量处理保证可靠。

#####为什么要使用Spark？#####

但是这种方法有一定的代价：你需要在两个不同的系统中实现和维护两套相同的业务逻辑。举个例子，如果你的批处理系统是基于Apache Hive或者Apache Pig实现的，而实时系统是基于Apache Storm实现的，那么你需要分别用SQL和Java编写和维护同样的汇总逻辑。就像Jay Kreps的文章[Questioning the Lambda Architecture](http://radar.oreilly.com/2014/07/questioning-the-lambda-architecture.html)提到的那样，这种情况会很快变成运维噩梦。

如果我们是基于Hive为这个客户实现的POC系统，我不得不告诉他们：“不，已经没有足够的时间让我们基于Storm重新实现整个业务逻辑了。”，不过幸运的是，我们用的是[Apache Spark](http://spark.apache.org/)，而不是Hive。

Spark是一个有名的机器学习框架，不过它同样很适合做ETL任务。Spark有一套简洁易用的APIs（比MapReduce可读性强，也没有MapReduce那么呆板），它的REPL接口还允许跟业务人员快速的进行业务逻辑原型设计。很显然，如果汇总数据执行的显著比MapReduce快的话，是没有人会抱怨的。

在这个实例中，Spark给我们带来的最大好处是Spark Streaming，它让我们能够在实时流处理中重用为批处理编写的汇总程序。我们不需要重新实现一套业务逻辑，也不用测试、维护另一套代码。这样的话，我们就可以迅速的在剩余的有限时间内部署一套实时系统 - 给用户、开发人员，甚至他们的管理层都留下了深刻的印象。

#####DIY#####

这里用一个简单的例子来说明我们是怎么做的。简单起见，只列出了最重要的步骤，可以点[这里](https://github.com/gwenshap/SparkStreamingExample)查看完整的源码。

+ 1 首先，我们写了一个函数来实现业务逻辑。在这个例子里面，我们想要从一系列事件日志中统计每天的errors的数量。这些日志由日期、时间、日志级别、进程以及日志内容组成：
<pre>
14/08/07 19:19:26 INFO Executor: Finished task ID 11
</pre>
为了统计每天的errors数量，我们需要对每天的日志按照日志等级过滤，然后进行计数：
<pre>
def countErrors(rdd: RDD\[String\]): RDD\[(String, Int)\] = {
  rdd
    .filter(\_.contains("ERROR")) // Keep "ERROR" lines
    .map( s => (s.split(" ")(0), 1) ) // Return tuple with date &amp; count
    .reduceByKey(\_ + \_) // Sum counts for each date
}
</pre>
<p>在上述函数中，我们过滤保留了所有含有“ERROR”的行，然后用一个map函数，将每一行的第一位，也就是日期作为key。然后运行一个reduceByKey函数计算得到每天的errors数量。</p>
<p>如我们所见，这个函数将一个RDD转换成另一个。RDD是Spark的[主要数据结构](http://spark.apache.org/docs/latest/programming-guide.html#resilient-distributed-datasets-rdds)。Spark对用户隐藏了处理分布式数据集的复杂操作，我们可以像处理其他任何数据那样处理RDD。</p>

+ 2 我们可以在Spark ETL过程中使用这个函数，从HDFS读取数据到RDD，统计errors，然后将结果保存到HDFS：
<pre>
val sc = new SparkContext(conf)
val lines = sc.textFile(...)
val errCount = countErrors(lines)
errCount.saveAsTextFile(...)
</pre>
<p>在这个例子里面，我们初始化一个SparkContext来在Spark集群中执行我们的代码。（注：在Spark REPL中我们不必自己初始化SparkContext，REPL自动做了初始化）SparkContext初始化完成之后，我们用它来从文件读取数据到RDD，执行我们的计数函数，然后将结果保存到文件。</p>
<p>spark.textFile and errCount.saveAsTextFile接收的URLs参数可以是hdfs://…，本地文件系统，Amazon S3或者其他的文件系统。</p>

+ 3 现在，假设我们不能等到一天结束之后再去统计errors，而是每分钟都想更新每天的errors数量。我们不用重新实现汇总方法 - 我们只需要在streaming代码里面重用它：
<pre>
val ssc = new StreamingContext(sparkConf, 60)
// Create the DStream from data sent over the network
val dStream = ssc.socketTextStream(args(1), args(2).toInt, StorageLevel.MEMORY_AND_DISK_SER)
// Counting the errors in each RDD in the stream
val errCountStream = dStream.transform(rdd => ErrorCount.countErrors(rdd))
// printing out the current error count
errCountStream.foreachRDD(rdd => {
      System.out.println("Errors this minute:%d".format(rdd.first()._2))
})
// creating a stream with running error count
val stateStream = errCountStream.updateStateByKey\[Int\](updateFunc)
// printing the running error count
stateStream.foreachRDD(rdd => {
      System.out.println("Errors today:%d".format(rdd.first()._2))
})
</pre>
<p>我们又一次初始化了一个上下文，这次是SteamingContext。SteamingContext监听一个数据流事件（这个例子里面是监听网络socket，产品环境下，我们通常使用像Apache Kafka这样更可靠的服务），然后将数据转换成一个RDDs流。</p>
<p>每一个RDD表示了一个微批量的流。每个微批量的时间窗是可以配置的（这个例子里面设置的是60秒一个批量），可以用来平衡吞吐量（大批量）和延迟（小批量）。</p>
<p>我们在DStream上跑一个map操作，使用countErrors函数，将流里面每一行数据组成的RDD转换成(date, errorCount)的RDD。</p>
<p>对于每一个RDD，我们输出每一个批量的error数量，然后用同一个RDD来更新总的error数（天的总数）的流。我们用这个流来打印总数。</p>

简单起见，我们这里将输出打印到屏幕，这里也可以输出到HDFS、Apache HBase或者Kafka（实时程序和用户可以使用它）。

#####结论#####

总的来说：Spark Streaming让你只需要实现一次业务逻辑，然后在批量ETL处理、流式处理中重用这个实现。在前述的客户使用场景中，Spark让我们可以基于批量处理快速（几个小时之内）实现一个实时数据处理层，这个时髦的demo给了我们的客户一个深刻的印象。然而这不仅仅让我们短期受益，从长期来看，这个架构只需要少量的运维开销，同时也减少了因为多套代码导致错误的风险。

#####感谢#####

感谢Hari Shreedharan, Ted Malaska, Grant Henke和Sean Owen的贡献和反馈。

Gwen Shapira是Cloudera的软件工程师（之前是解决方案架构师）。她也是O’Reilly出版的Hadoop Application Architectures一书的作者之一。

<div class="meta_info">
<p><span>[译文信息]</span></p>
<p>原文作者: Gwen Shapira (@gwenshap)</p>
<p>原作时间: 2014-08-29</p>
<p>原作链接: http://blog.cloudera.com/blog/2014/08/building-lambda-architecture-with-spark-streaming/</p>
</div>
