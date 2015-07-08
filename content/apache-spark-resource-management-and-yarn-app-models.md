Title: [翻译] Apache Spark资源管理和YARN应用程序模型
Slug: apache-spark-resource-management-and-yarn-app-models
Date: 2015-06-26
Category: Spark
Author: 杨文华
Tags: Spark, YARN
Type: 翻译
OriginAuthor: Sandy Ryza
OriginTime: 2014-05-30
OriginUrl: http://blog.cloudera.com/blog/2014/05/apache-spark-resource-management-and-yarn-app-models/


**Spark和MapReduce使用YARN管理集群资源的简单比较。**

继MapReduce之后，最著名的Apache YARN应用要数Apache Spark了。在Cloudera，我们通过努力让Spark-on-YARN（[SPARK-1101](https://issues.apache.org/jira/browse/SPARK-1101)）保持稳定，并在CDH 5.0.0中加入了对Spark的支持。

通过这篇文章你可以学习Spark和MapReduce在架构上的区别，了解你为什么要关注这个问题的原因，以及搞清楚它们是怎样在YARN集群资源管理系统上运行的。


#####应用程序#####

在MapReduce中，计算的最上层单元是是job。系统加载数据，执行一个map函数，shuffle数据，执行一个reduce函数，然后将数据写回到持久化存储器。Spark有一个类似job的概念（虽然一个job可以由多个stage组成，而不是仅仅只包含map和reduce），不过Spark还有一个更高层级的概念叫做应用程序（application），应用程序可以以并行或者串行的方式跑多个job。

![pic1](/images/apache-spark-resource-management-and-yarn-app-models-f1.png)


#####Spark应用程序体系结构#####

熟悉Spark API的人都知道，一个应用程序对应着一个SparkContext类的实例。一个应用程序可以只用于一个批量计算的任务，或者一个包含了多个独立任务的交互式会话，再或是一个持续响应请求的服务。不同于MapReduce，一个应用程序拥有一系列进程，叫做executors，他们在集群上运行，即使没有job在运行，这些executor仍然被这个应用程序占有。这种方式让数据存储在内存中，以支持快速访问，同时让task快速启动成为现实。


#####Executors#####

MapReduce的每个task是在其自己的进程中运行的，当一个task结束，进程随之终结。在Spark中，多个task可以在同一个进程中并行的执行，并且这些进程常驻在Spark应用程序的整个生命周期中，即使是没有job在运行的时候。

上述Spark模型的优势在于速度：task可以快速的启动，处理内存中的数据。不过他的缺点是粗粒度的资源管理。因为一个应用程序的executor数量是固定的，并且每个executor有固定的资源分配，一个应用程序在其整个运行周期中始终占有相同数量的资源。（当YARN支持[container resizing](https://issues.apache.org/jira/browse/YARN-1197)时，我们计划在Spark中利用它，实现资源动态分配。）（译注：原文写于2014年05月30日）


#####活跃的Driver#####

Spark需要依赖一个活跃的driver（active driver）进程来管理job和调度task。一般的，这个driver进程跟启动应用程序的客户端进程是同一个，不过在YARN模式中（后面会讲到），driver进程可以在集群中运行。相反的，在MapReduce中，客户端进程在job启动之后可以退出，而job还会继续运行。在Hadoop 1.x中，JobTracker负责task的调度，在Hadoop 2.x中，MapReduce应用程序master接管了这个功能。


#####可插拔的资源管理#####

Spark支持可插拔的集群管理。集群管理系统负责启动executor进程。Spark应用程序开发人员不必担心到底使用的是哪一种集群管理系统。

Spark支持YARN、Mesos以及自带的Standalone集群管理系统。这三个系统都包含了两个组件。一个master服务（YARN ResourceManager、Mesos master或Spark standalone master），他会决定哪个应用程序运行executor进程，同时也决定在哪儿、什么时候运行。每个节点上运行一个slave服务（YARN NodeManager, Mesos slave或者Spark standalone slave），slave实际启动executor进程。资源管理系统同时还监控服务的可用性和资源消耗。


#####为什么要使用YARN#####

使用YARN来管理集群资源较使用Spark standalone和Mesos有一些优势：

+ YARN集中配置一个集群资源池，允许运行在YARN之上的不同框架动态共享这个资源池。你可以用整个集群跑一个MapReduce任务，然后使用其中一部分做一次Impala查询，另一部分运行一个Spark应用程序，并且完全不用修改任何配置。

+ 你可以利用YARN的所有调度特性来做分类、隔离以及任务优先。

+ 最后，YARN是唯一支持Spark安全特性的集群资源管理系统。使用YARN，Spark可以在Kerberized Hadoop之上运行，在它的进程之间使用安全认证。


#####在YARN上运行Spark#####

当在YARN上运行Spark时，每个Spark executor作为一个YARN container运行。MapReduce为每一个task生成一个container并启动一个JVM，而Spark在同一个container中执行多个task。Spark的这种方式让task的启动时间快了几个量级。

Spark支持以yarn-cluster和yarn-client两种模式在YARN上运行。明显的，yarn-cluster用于产品环境较为合理，而yarn-client更适合用在交互式调试的场景中，它能让开发者实时的看到应用程序的输出。

要想理解这两种模式的区别，需要先理解YARN应用程序的master概念。在YARN中，每个应用程序实例都有一个master进程，它是为应用程序启动的第一个container。应用程序负责从ResourceManager申请资源，同时分配这些资源，告诉NodeManagers为该应用程序启动container。master的存在，就可以避免一个活跃的客户端 - 启动程序的进程可以退出，而由YARN管理的进程会继续在集群中运行。

在yarn-cluster模式中，driver在master上运行，这意味着这个进程同时负责驱动应用程序和向YARN申请资源，并且这个进程在YARN container中运行。启动应用程序的客户端不用常驻在应用程序的运行周期中。下图是yarn-cluster模式：

![pic1](/images/apache-spark-resource-management-and-yarn-app-models-f2.png)

然而yarn-cluster并不太适合交互式的Spark实用场景。需要用户输入，如spark-shell和PySpark，需要Spark deriver在启动应用程序的客户端进程中运行。在yarn-client模式中，master仅仅出现在向YARN申请executor container的过程中。客户端进程在containers启动之后，与它们进行通讯，调度任务。下图是yarn-client模式：

![pic1](/images/apache-spark-resource-management-and-yarn-app-models-f3.png)

下图的表格简要的给出了这两种模式的区别：

![pic1](/images/apache-spark-resource-management-and-yarn-app-models-f4.png)


#####核心概念#####

+ 应用程序（Application）：应用程序可以是一个单独的job，也可以是一系列的job，或者是一个持续运行的可以进行交互的会话服务。

+ Spark Driver：Spark driver是在Spark上下文（代表一个应用程序会话）中运行的一个进程。Driver负责将应用程序转化成可在集群上运行的独立的步骤。每个应用程序有一个driver。

+ Spark Application Master：master负责接受driver的资源请求，然后向YARN申请资源，并选择一组合适的hosts/containers来运行Spark程序。每个应用程序有一个master。

+ Spark Executor：在计算节点上的一个JVM实例，服务于一个单独的Spark应用程序。一个executor在他的生命周期中可以运行多个task，这些task可以是并行运行的。一个节点可能有多个executor，一个应用程序又会有多个节点在运行executor。

+ Spark Task：一个Spark Task表示一个任务单元，它在一个分区上运行，处理数据的一个子集。

#####阅读更多#####
+ [Spark文档](https://spark.apache.org/docs/latest/cluster-overview.html)
+ [Cloudera的在YARN上运行Spark应用程序文档](http://www.cloudera.com/content/cloudera-content/cloudera-docs/CDH5/latest/CDH5-Installation-Guide/cdh5ig_running_spark_apps.html)

原文作者Sandy Ryza是Cloudera的数据科学家，同时还是Apache Hadoop的贡献者。