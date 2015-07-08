Title: [翻译] Apache Spark性能调优（二）
Slug: how-to-tune-your-apache-spark-jobs-part-2
Date: 2015-06-24
Category: Spark
Author: 杨文华
Tags: Spark, YARN, Tuning
Type: 翻译
OriginAuthor: Sandy Ryza
OriginTime: 2015-03-30
OriginUrl: http://blog.cloudera.com/blog/2015/03/how-to-tune-your-apache-spark-jobs-part-2/


这篇文章是Apache Spark性能调优的第二部分，延续[Apache Spark性能调优（一）](/how-to-tune-your-apache-spark-jobs-part-1.html)。本文尝试涵盖几乎所有让Spark程序高效运行的问题。首先，你会学习资源调优，或者说通过配置，最大限度的利用Spark集群提供的所有资源；然后会学习并行调优，并行度是影响job性能的调优最困难同时也是最重要的参数；最后你会学到数据本身的表现形式，存储在磁盘上供Spark读取的形式，以及在内存中作为cache或者传输的形式。


#####资源分配调优#####

在Spark用户邮件组里面充斥着类似这样的一些问题：“我有一个500个节点的Spark集群，但是当我跑一个应用程序时，只有两个tasks同时执行，不应该啊，怎么破？”。考虑到Spark有如此多的参数来控制Spark集群资源的使用，产生这些问题也还不算不合理。在这一部分，你可以学习怎样尽可能多的使用Spark集群的所有资源（榨干你的Spark集群）。不同的集群管理系统（YARN、Mesos、Spark Standalone）的推荐配置会有一些差别，这里我们只关注YARN，Cloudera也建议所有用户使用YARN。

选择YARN的背景以及在YARN上运行Spark的更详细资料可以参见[Apache Spark Resource Management and YARN App Models](http://blog.cloudera.com/blog/2014/05/apache-spark-resource-management-and-yarn-app-models/)。

Spark（以及YARN）关注的最主要的两个资源是CPU和内存。磁盘和网络I/O当然也是影响Spark性能的一部分因素，但是Spark和YARN目前在这方面都没有什么动作。

Spark应用程序的每个executor都有相同的固定的CPU核数，以及相同的固定的堆（heap）大小。在执行spark-submit, spark-shell, 和pyspark时，CPU核数可以通过--executor-cores来指定；CPU核数也可以通过在spark-defaults.conf文件或者SparkConf对象中设置spark.executor.cores来指定。类似的，堆大小也可以通过--executor-memory（译者注：原文这里应该是笔误写成了--executor-cores）或者spark.executor.memory来指定。CPU核数控制每个executor可以并行运行的task数量。设置“--executor-cores 5”意思是每个executor最多可以同时跑5个任务。堆大小（spark.executor.memory）影响Spark能够cache的数据量，同时影响用于做group、aggregation、join时产生的shuffle的数据结构的内存大小。

可以通过设置--num-executors或者spark.executor.instances来控制申请的executor数量。从CDH 5.4/Spark 1.3开始，如果通过设置spark.dynamicAllocation.enabled属性开启了[动态分配executor（dynamic allocation）](https://spark.apache.org/docs/latest/job-scheduling.html#dynamic-resource-allocation)就可以不用自己设置executor数量。动态分配executor可以让一个Spark应用程序在有task积压时申请增加executor，在executor变为idle状态时释放executor。

考虑Spark申请的资源怎样与YARN的可用资源相适应也是比较重要的。相关的YARN属性如下：

+ yarn.nodemanager.resource.memory-mb控制一个节点上所有container可用的内存总和。

+ yarn.nodemanager.resource.cpu-vcores控制一个节点上所有container可用的CPU核数总和。

给executor申请5个核（cores）结果是向YARN申请5个虚拟核（virtual cores）。从YARN申请内存会复杂一些：

+ --executor-memory/spark.executor.memory控制executor的堆大小，但是JVMs同时还会使用一部分的堆外内存，比如interned Strings和direct byte buffers。每个executor最终向YARN申请的总内存还需要加上spark.yarn.executor.memoryOverhead，这个属性的默认值是max(384, 0.07 * spark.executor.memory)，单位是MB。

+ YARN可能会对申请的内存做上舍入。YARN的yarn.scheduler.minimum-allocation-mb和yarn.scheduler.increment-allocation-mb属性分别控制了最小分配内存大小和申请的增量大小。

下图显示了Spark和YARN中的内存属性层级（默认不伸缩）：

![pic1](/images/how-to-tune-your-apache-spark-jobs-part-2-f1.png)

最后还有其他一些关于Spark executor的配置需要考虑：

+ 应用程序master是一个非executor的container，它负责从YARN申请containers。在yarn-client模式下，master的默认配置是1024MB内存和一个vcore；在yarn-cluster模式下，master同时还会跑driver，这时候配置--driver-memory和--driver-cores属性就比较重要了。

+ 给executor配置过多的内存常常会导致过多的垃圾回收。粗略估计，每个executor的内存大小最好不要超过64GB。

+ 我注意到HDFS client在大量线程并行操作时会出现一些问题。粗略估计，每个executor并行5个task就可以达到最高的写吞吐量，所以每个executor的核数最好不要超过5个。

+ 小executor（比如executor都设置成1核和只足够跑一个task的内存大小）无法利用同一个JVM跑多个task的优势。比如，每个executor都需要复制一份广播变量，很多的小executor会导致广播需要复制很多份。

更具体一些，这里给出一个最大限度的使用集群资源的实例：假设你有一个Spark集群，其中6个节点上跑了NodeManagers，每一个节点有16核、64GB内存。假设NodeManager的yarn.nodemanager.resource.memory-mb和yarn.nodemanager.resource.cpu-vcores分别设置成63 * 1024 = 64512MB和15。我们不会给YARN container分配节点所有的机器资源，因为节点的OS和Hadoop daemons还需要占用一些资源。这个例子里面，我们预留1GB和1核给这些系统进程。Cloudera Manager可以帮助自动计算和配置这些YARN属性。

也许最直接的配置是：--num-executors 6 --executor-cores 15 --executor-memory 63G，但这样是不对的：

+ 63GB加上spark.yarn.executor.memoryOverhead超过了NodeManager的63GB内存限制。

+ master会用掉其中一个节点的一个核，就是说那个节点上容纳不了一个15核的executor。

+ 每个executor15个核达不到很好的HDFS I/O吞吐量。

一个较好的配置是：--num-executors 17 --executor-cores 5 --executor-memory 19G。为什么？

+ 这个配置，除了master所在的节点分配了两个executor之外，其他节点都分配了三个executor。

+ --executor-memory是通过(每个节点使用63/3的内存) = 21，21 * 0.07 = 1.47，21 – 1.47 ~ 19推导出来的。


#####并行化调优#####

读到这里，你应该已经知道Spark是一个并行处理引擎。不过不那么明显的是，Spark并不是一个“神奇”的并行处理引擎，它在一定限制条件下实现最大化的并行。每个Spark的stage包含一定数量的task，这些task是顺序执行的。在Spark调优中，stage中的task数量应当说是影响性能最重要的一个参数了。

但是这个数量是如何确定的呢？Spark将RDDs合并成stages的方式在[前一部分](/how-to-tune-your-apache-spark-jobs-part-1.html)中已经讲过了。快速回顾一下，像repartition、reduceByKey这样的transformation会产生stage边界。一个stage中的task数量等于这个stage中的最后那个RDD的分区数量。一个stage中，一个RDD的分区数量又等于它所依赖的RDD的分区数量，除了几个例外：coalesce允许生成一个分区数比它依赖的RDD少的RDD，union生成一个分区数是它的父RDDs分区数的和的RDD，cartesian生成一个分区数是它的父RDDs分区数的乘积的RDD。

那没有父RDDs的RDD呢？由textFile或者hadoopFile生成的RDDs，他们的分区数量取决于所使用的底层MapReduce InputFormat。通常一个HDFS block就会生成一个分区。由parallelize生成的RDDs的分区数量，可以在程序中给定，如果没有给定就会使用spark.default.parallelism这个配置的值。

可以调用rdd.partitions().size()来确定一个RDD中的分区数量。

一个主要的问题是task的数量过于少。假如task的数量比可用的槽位（slot）少的话，这个stage就不能利用全部可用的CPU。

Task数量太少同时还意味着每个task中的所有聚合操作都面临更大的内存压力。所有join、cogroup、\*ByKey操作都涉及到将一些对象放到hashmaps或in-memory buffers中，以做分组或排序。join、cogroup、groupByKey在它们触发的shuffle的下游的stage中的task中使用这些数据结构；而reduceByKey和aggregateByKey在它们触发的shuffle的两边的stage中的task里面使用这些数据结构。

当给聚合操作的数据不能装入内存时，会出现一些严重问题。首先，将大量的数据保存在这些数据结构中会给垃圾回收带来压力；其次，当数据不能装入内存，Spark会将他们溢写（spill）到磁盘，产生磁盘I/O和排序。这种在大shuffle情况下产生的问题，或许是我在Cloudera客户中见过的任务失败的头号诱因。

那么怎样增加分区的数量呢？如果这个stage是来自于从Hadoop读取数据，你有这几个选择：

+ 使用repartition操作，他会触发一次shuffle。

+ 配置InputFormat创建更多的切分。

+ 将输入数据以更小的块写到HDFS。

如果一个stage是从另外的stage得到的输入数据，触发stage边界的transformation可以接受一个numPartitions参数，就像：

<pre>
val rdd2 = rdd1.reduceByKey(_ + _, numPartitions = X)
</pre>

那么X应该取什么值呢？优化这个分区数量的最直接的方式是实验：先得到它的父RDD的分区数量，然后不断将这个数乘以1.5直到性能不再增加。

也有一个更学术的方法可以计算X的值，不过给定一个先验值比较困难，因为有些数量难以计算。我在这里提到这种方法，不是因为推荐它做一种常规方法，而是因为它可以帮助我们理解其中的原理。我们的目标是运行足够的task，以使所有输入给task的数据都能够装入到task的可用内存中。

每个task的可用内存等于(spark.executor.memory * spark.shuffle.memoryFraction * spark.shuffle.safetyFraction)/spark.executor.cores，spark.shuffle.memoryFraction和spark.shuffle.safetyFraction的默认值分别是0.2和0.8。

所有shuffle的数据在内存中的大小难以确定。最接近的尝试是找到这个stage的Shuffle Spill（内存）和Shuffle Spill（Disk）的比例，然后乘以总的shuffle数量。然而，如果stage在做归约（reduction）的话，计算就比较复杂了。

![pic2](/images/how-to-tune-your-apache-spark-jobs-part-2-f2.png)

然后做一个上舍入，因为更多的分区总是比更少的分区好一些。

事实上，可能有人会有疑问，为何更多的task（以及更多的分区）更好。这个建议与MapReduce中的建议是相反的，MapReduce中要求你对task的数量保守一些。这里面的不同之处在于MapReduce启动一个任务的开销很高，而Spark不是。


#####为你的数据结构瘦身#####

数据是以数据记录（record）的形式流经Spark的。一条记录有两种表现形式：反序列化的Java对象的形式和序列化的二进制的形式。一般而言，Spark在内存中使用数据记录的反序列化形式，而当数据记录存储在磁盘或者做网络传输时，使用序列化的形式。目前有一些[计划好的](https://issues.apache.org/jira/browse/SPARK-2926)[工作](https://issues.apache.org/jira/browse/SPARK-4550)在将某些in-memory shuffle数据以序列化的方式来存储。

spark.serializer这个属性控制数据在这两种表现形式之间的转换方式。Kryo序列化方式对应org.apache.spark.serializer.KryoSerializer，是推荐的选项。不幸的是，在早期的Spark版本中，Kryo有一些不稳定性问题，后期版本为了不破坏兼容性，并没有把Kryo作为默认选项。不过开发人员还是应当首选Kryo来做序列化。

数据记录在这两种表现形式下的大小对Spark的性能有很大的影响。检查数据结构，尽量削减数据结构的大小是很值得做的一件事情。

臃肿的反序列化对象会导致Spark更多的溢写数据到磁盘，同时减少了Spark可以cache（比如在MEMORY storage level模式下）的反序列化数据记录的数量。Spark调优有一个很好的[章节](http://spark.apache.org/docs/1.2.0/tuning.html#memory-tuning)专门来讲数据结构的瘦身。

臃肿的序列化对象会导致更多的磁盘和网络I/O，同时减少了Spark可以cache（比如在MEMORY_SER storage level模式下）的序列化数据记录。这里要注意的是你需要确保使用SparkConf#registerKryoClasses这个API来对自定义的类进行注册。


#####数据格式#####

如果你可以决定数据存储在磁盘上的方式，那么你应当选择一种可扩展的二进制数据格式，例如Avro，Parquet，Thrift或者Protobuf。选择其中一种数据格式，并且一直都用这种格式。说的更明白一点，当谈及在Hadoop上使用Avro，Thrift或者Protobuf，意思应该是每条数据记录都是用Avro/Thrift/Protobuf格式存储在文件中的。JSON格式不值得尝试。

每次当你考虑将大量的数据以JSON格式存储时，你可以联想一下中世纪将要产生的冲突与对立，加拿大将要被大坝拦截的美丽河流，或者是将要在美国腹地建造的为了给你解析文件的CPU提供能源的核设施产生的核泄漏（译者注：原作者是诗人吗...）。同时，学习一点人际交往能力，以使你能够说服你的同僚和上级也不要使用JSON格式存储数据。

原文作者Sandy Ryza是Cloudera的数据科学家，他同时还为Apache Hadoop和Apache Spark项目贡献代码。他是O’Reilly出版的[Advanced Analytics with Spark](http://shop.oreilly.com/product/0636920035091.do)一书的作者之一。