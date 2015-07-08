Title: [翻译] 使用Apache Hadoop进行准实时数据处理的架构模式
Slug: Architectural_Patterns_for_Near_Real-Time_Data_Processing_with_Apache_Hadoop
Date: 2015-06-25
Category: Spark
Author: 黄兴
Tags: Spark, Streaming
Type: 翻译
OriginAuthor: Ted Malaska
OriginUrl: http://blog.cloudera.com/blog/2015/06/architectural-patterns-for-near-real-time-data-processing-with-apache-hadoop/


##### 使用Apache Hadoop进行准实时数据处理的架构模式

**评估哪一种流处理架构模式最适合自己的用例是成功进行生产环境布署的前提。**

对于想要实时地处理和理解大规模数据的企业，Apache Hadoop生态系统已经成为了受到亲睐的平台。像Apache Kafka, Apache Flume, Apache Spark, Apache Storm和Apache Storm这样的技术正在将一切变得可能。人们经常将大规模流处理的用例归于一起，但是现实是这些用例更适于被分成不同的架构模式, 对于不同的问题，更宜采用这个生态系统中的不同组件。

在这篇文章中，我将要列出主要的流处理模式，它们是我们的客户在生产中运行企业级数据中心时采用的模式，我也将解释如何在Hadoop上实施这些模式。

##### 流处理模式

这四种基本的流处理模式(经常被一起使用)是：

- **流摄取(Stream ingestion):** 以低延迟把消息持久化到HDFS, Apache HBase和Apache Slor.
- **依赖外部上下文的准实时事件处理(Near Real-Time Event Processing with External Context):** 在消息到来后进行报警、打标签、转换以及过滤等动作。这些动作可以依据复杂的标准做出，比如异常检测模型。通常的用例，包括准实时地欺诈检测和推荐，经常需要100毫秒以下的延迟。
- **准实时事件分区处理(NRT Event Partitioned Processing)：**和准实时事件处理很相似，但是准实时事件分区处理可以从对数据进行分区中获益——比如把更加相关的外部信息放在内存中(译注：即把数据分区，同时把事件处理所需要的外部信息也分区，使其能放入内存。详见底下的具体叙述)。这种模式把要求100毫秒以下的处理时延。
- **用于聚合或机器学习的复杂拓扑(Complex Topology for Aggregations or ML)：** 流处理的圣杯：使用复杂和灵活的操作集合从数据中实时获取答案。因为结果通常更依赖于窗口计算(windowsed computations)并且需要更多的活动数据(active data)，所以焦点从更低的时延转移到了功能和准确性。

接下来的章节，我们将介绍如何使用被推荐的方式来实现这些模式，并且以一种被测试过、证明了以及可维护的方式来实现它们。

##### 流摄取(Stream Ingestion)

传统上，采用Flume来做流摄取是一种被推荐的方式。Flume大量的source和sink库包括了所有需要消费和写入的情况。(如果想要了解如何配置和管理Flume, [Using Flume](http://shop.oreilly
.com/product/0636920030348.do "Using Flume")是一个不错的资料)

在过去的一年中，Kafka也因为它的强大的特性，比如回放(playback)和复制(replication)，而流行起来。因为Flume和Kafka和目标方面的重叠，它们的关系经常令人疑惑。它们是如何协作呢？答案很简单：Kafka是一个类似于Flume Channel的管道， 尽管由于上面提到的特性，它是一个更好的管道。经常采用的策略是使用Flume做为source和sink，而Kafka作为中间的管道。

下面的图表展示了如何把Kafka作为Flume的上流数据源，以及Flume的下流数据池，或者Flume Channel。

![pic1](/images/streampatterns-f1.png)

下图展示的设计可以大规模扩展，拥有实战强度，可以通过Cloudera Manager进行集中监控，拥有容错能力，以及支持重放。

![pic2](/images/streampatterns-f2.png)

在我们介绍下一个流处理架构之前，我们需要先说明这种设计是如何优雅地容错的。Flume Sinks从Kafka消费者组(Kafka Consumer Group)中拉取消息。消费者组依靠Apache Zookeeper追踪Topic的offset(译注：指追踪消费的进度)。如果一个Flume Sink失效了，Kafka消费者组将会把负载分配到剩余的sink中。当失效的Flume Sink恢复以后，消费者组将会重新分配(译注：指将会重新平衡负载)。

##### 依赖外部上下文的准实时事件处理

重申一下，这种模式的一个通常用例是监视事件消息流入，并且立即做出决策，要不就对消息进行转换，要不就采取某种外部动作。决策的逻辑通常依赖于外部的资料或者元数据。实现这种用例的一种简单并且可扩展的方式是增加一个Flume Sink 拦截器或者 Source拦截器到你的Kafka/Flume架构中。采用中等适度地调优，不难实现较低毫秒级的延迟。

Flume的拦截器能够拦截一个或者一批消息，并且允许用户代码来修改它们或者依据它们采取动作。用户代表可以与本地内存或者一个外部的存储系统，像是HBase,进行交互，来获取做出决策所需的资料。根据网络情况、schema设计以及配置，HBase可以以大概4-25毫秒的时延提供信息。你也可以通过配置HBase，使其不会失效或者暂停工作，即使是遇到了节点失效的情况。

![pic3](/images/streampatterns-f3.png)

实现这种方案在Flume拦截器的逻辑之外，几乎不需要其它的代码。Cloudera Manager提供了一个直观的UI来对你的逻辑进行打包布署，以及连接进系统、配置以及监控你的服务。

##### 依赖外部上下文的准实时的分区的事件处理

在下图所示的架构中(无分区的解决方案)中，你可以需要频繁地调用HBase，因为与事件处理相关的上下文由于太大而不能放在Flume拦截器的本地存储中。

![pic4](/images/streampatterns-f4.png)

但是，如果你定义了一个key,来对数据进行分区，你就可以把流入的数据与上下文数据中与其相关的子集进行区配。如果你把数据分成10份，你就只需要保留1/10的数据在内存中。HBase很快，但是本地内存更快。Kafka允许你定义一个自己的分区器(partitioner)来对数据进行会区。

需要说明的是在这里Flume不是必须的；这里最根本的需求只有Kafka的消费者。所以，你可以使用在Yarn上的consumer或者一个只有Map的MapReduce程序。

##### 用于聚合或者机器学习的复杂拓扑

到此为止，我们都是在探索事件级别的操作。但是，有些时候你需要更加复杂的操作，比如计数、求平均、会话或者构造机器学习模型这些需要对于一批数据进行的操作。在这种情况下， Spark Stream是一种理想的工具，原因有以下几点：

* **与其它工具相关，开发更简单**

    Spark丰富和简洁的API使得构造复杂的拓扑更加简单

* **相似的代码可以同时用于流处理和批处理**

    只需要进行一些改变，用于实时小批量处理的代码就可以用于极大规模的离线批处理。不仅能减少代码数量，还能减少用于测试和整合的时间。
  
* **只需要了解一个引擎**

    培养人员来了解分布式处理引擎的怪癖和内部特性需要一些开销。使用Spark统一了在流处理和批处理两方面的此项开销。
  
* **微批量(micro-batching)可以帮助你可靠地扩展**

    在batch层面上进行确认(acknowledging)(译注：就是批处理中的术语ack)可以实现更大的吞吐量以及可以用以构建无需担心重复发送的解决方案。微批量对于将更新发送到HDFS或者HBase的情况，也可以有助于实现性能的扩展。

* **与Hadoop生态系统的整合已经成熟可用**

    Spark与HDFS, HBase和Kafka有深度地整合。
  
* **没有数据丢失的风险**

    由于WAL和Kafka, Spark Streaming可以在出现故障时避免数据丢失。
  
* **易于调试和运行**

    你可以在本地的IDE上调试和单步运行你自己的Spark Streaming代码，而不需要一个集群。而有，Spark Stream的代码就像是普通的函数式编程的代码，所以Java和Scala开发人员并不需要花费很多时间来转到Spark Streaming。(也支持Python)

* **流是原生的有状态的**

    在Spark Streaming中，状态是一等公民，这意味着可以很容易地写出有状态的流处理程序，并且可以应对结点故障。
  
* **作为事实上的标准，Spark正在获得整个生态系统的长期投资**

    在写这篇文章的时候，在过去的30天里有接近700个对Spark代码的提交(commit)，与其它的流处理框架相比，比如Storm在同期只有15个提交。
  
* **你可以使用ML库**

    Spark的机器学习库MLib正在变得非常流行并且它的功能也会需要。
  
* **你可以在需要的地方使用SQL**

    使用SparkSQL, 你可以在你的流处理程序中加入SQL逻辑来降低代码的复杂性。
  
##### 结论

流处理有很多能力，也有一些可能的模式，但是就像你在这篇文章里学到的一样，如果你选择了适用于你的用例的模式，你就可以用很少的代码实现很强大的能力。

作者Ted Malaska是Cloudera的解决方案架构师，同时也是Apache Spark, Flume以及HBase的贡献者，也是O'Reilly的[Hadoop Applications 
Architecutre](http://shop.oreilly.com/product/0636920033196.do "Hadoop Applications Architecture")一书的作者之一。




  

















