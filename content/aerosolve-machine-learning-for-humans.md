Title: Airbnb开源机器学习框架Aerosolve
Slug: aerosolve-machine-learning-for-humans
Date: 2015-07-08
Category: Spark
Author: 杨文华
Tags: Aerosolve, Spark, Machine Learning, Airbnb
Type: 翻译
OriginAuthor: Hector Yee & Bar Ifrach
OriginTime: 2015-06-04
OriginUrl: http://nerds.airbnb.com/aerosolve/


你是否曾想过Airbnb给房东的价格提示是怎么实现的呢？

![pic1](/images/aerosolve-machine-learning-for-humans-1.gif)

在这个[动态定价](http://en.wikipedia.org/wiki/Dynamic_pricing)功能里，我们给房东显示产生订单的概率（绿色表示几率大，红色表示几率小），或者说预测的订单量，让房东能够简单的点点按钮，就能够对他们的房源进行动态调价。

有很多特征会季节性的参与到房源订单预测中，针对房源和价格的独特特征。这些特征之间以复杂的方式进行相互作用，结果是机器学习模型难以解释。于是我们开始开发一个机器学习包，帮助产生可解释、可理解的机器学习模型。这对我们的开发人员和用户都有很大帮助，可解释性意味着我们可以向房东解释，为什么他们得到的实际订单量比他们期望的订单量低或者高。

引入Aerosolve：一个为人类构建的机器学习包。

我们已经实践了让人和机器（机器学习）搭档共同工作的理念，其结果也超过了人或者机器单独工作的效果。

从项目初期，我们就致力于通过易于理解的模型协助人们解释复杂的数据，以改善对数据集的理解。Aerosolve模型将数据暴露出来让人们易于理解，而不是将其含义隐藏在模型错综复杂的层次之中。

举个例子，我们可以简单的通过下图，得到一个房源在市场上的价格与其产生的订单之间的负相关关系。我们让模型很宽，每一个变量或者变量的组合，都用一个明确的[附加函数](http://en.wikipedia.org/wiki/Generalized_additive_model)来建模，而不是将特征传给很多个非线性的深深隐藏的层。这使得模型易于解释，同时保证了学习能力。

![pic2](/images/aerosolve-machine-learning-for-humans-2.png)

*图1 模型权重 vs. 市场价格百分比*

图中的红线表示的是经验值，在这个实例中，我们通常认为需求会随着价格的增加而下降。在Aerosolve中，我们可以通过一个简单的文本配置，把经验值添加到训练过程中，影响模型。图中的黑线是用数百万数据学习得到的模型的值，模型使用实际数据修正了人的假设，同时允许人为设置变量初始值。

我们对全球的社区进行建模，基于Airbnb房源的位置信息，通过算法自动生成本地社区。这跟手工实现的[社区多边形](http://nerds.airbnb.com/mapping-world/)有两个不同之处。首先，它们是自动创建的，我们可以为[新建市场](http://blog.airbnb.com/cuba/)快速构建社区信息；其次，它们是分层构建的，我们可以快速可扩展的累积点状（如房源浏览）或者多边形（如搜索结果）的统计信息。

分层还让我们能够借助上层社区的统计优势，上层社区完全包含子社区。这些使用Kd-tree构建的社区对用户是不可见的，但是它们会用于计算一些地域特征，并最终应用在机器学习模型中。我们用下图展示Kd-tree数据结构自动创建本地社区的能力。这里，注意到我们让算法避免跨越较大的水域。即使是“金银岛”也会有它自己的社区。为了避免社区边界突然变化，我们采用了多种方法来平滑社区信息。你可以进一步阅读，在Github上的[Image Impressionism demo of Aerosolve](https://github.com/airbnb/aerosolve/tree/master/demo/image_impressionism)中，你能看到这种类型的平滑。

![pic3](/images/aerosolve-machine-learning-for-humans-3.png)

*图2 为San Francisco自动生成的本地社区示意图*

因为每一个房源都有它的独特之处，我们为Aerosolve创建了图像分析算法，负责处理房源的装修、内饰等细节。我们使用两种训练数据来训练Aerosolve模型，下图左侧模型是我们基于专业摄影师的打分训练得出的，右侧模型是在自然预定数据基础上训练得出的。

![pic4](/images/aerosolve-machine-learning-for-humans-4.png)

*图3 通过机器学习做图片排序。左侧：图片基于专业摄影师打分的训练结果排序。右侧：图片基于自然预定、点击、展现数据的训练结果排序。*

我们还负责很多其他计算任务，包括地域事件。例如下图，我们可以发现SXSW（译注：西南偏南，美国德克萨斯州州府奥斯汀举办的音乐节）期间Austin的住宿需求的增加，我们可能会让房东在这个需求高峰期开门迎客。

![pic5](/images/aerosolve-machine-learning-for-humans-5.png)

*图4 Austin的季节性需求*

有一些特征，例如季节性的需求天生就是“很尖的”。其他的一些特征，例如评论数量，则一般不应该体现出同样的剧烈波动。我们使用三次多项式曲线（cubic polynomial splines）来平滑那些比较平滑的特征，使用迪拉克δ函数（Dirac delta functions）来保留波动。例如，在表示评论数和三星数（总共5星）的关系时，没有评论和有一个评论之间存在很强的不连续性。

![pic6](/images/aerosolve-machine-learning-for-humans-6.png)

*图5 使用二项式曲线平滑特征*

最后，当所有的特征都转换、平滑之后，所有的这些数据会集成到一个价格模型中，这个模型有成千上万互相作用的参数，房东可以根据这个模型的预测结果，得到一个房源的定价带来订单的概率。

你可以通过Github检出[Aerosolve](https://github.com/airbnb/aerosolve)的源码。里面提供了一些[实例](https://github.com/airbnb/aerosolve/tree/master/demo)，阐述了怎样将Aerosolve应用到你自己的模型中，例如，教一个算法绘出一幅点彩画派风格的作品。例子里面还有一个基于美国人口普查数据预测收入的实例。

![pic7](/images/aerosolve-machine-learning-for-humans-7.gif)

*图6 Aerosolve学习绘出彩画派风格的作品*

<div class="meta_info">
<p><span>[译文信息]</span></p>
<p>原文作者: Hector Yee & Bar Ifrach</p>
<p>原作时间: 2015-06-04</p>
<p>原作链接: http://nerds.airbnb.com/aerosolve/</p>
</div>