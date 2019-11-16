#! /usr/bin/env python3
"""Re-create classifiers based on training data."""
import argparse
import logging.config
import math
import sys
from typing import Any, List, Tuple

import matplotlib.pyplot as plt
import numpy as np
import yaml
from sklearn.metrics import auc, roc_curve
from sklearn.model_selection import learning_curve
from sklearn.utils.multiclass import unique_labels
from tqdm import tqdm
from twitter_ml.classify.movie_reviews import MovieReviews
from twitter_ml.classify.sentiment import Sentiment
from twitter_ml.classify.utils import Utils

with open("logging.yaml", "rt") as f:
    logging.config.dictConfig(yaml.safe_load(f.read()))

logger = logging.getLogger(__name__)


def do_graphs(classifiers: List[Tuple[str, Any]], X, y):
    """
    Command method: output graphs.

    :param classifiers: list of classifiers
    :param X: test data
    :param y: test categories
    """
    # plot confusion matries in a grid
    subplots_cols = 4
    subplots_rows = math.ceil(len(classifiers) / subplots_cols)
    logger.debug("Plot dimensions: %d x %d", subplots_rows, subplots_cols)

    fig, axs = plt.subplots(subplots_rows, subplots_cols, figsize=(15, 8))
    graph_data = list(zip(axs.flat, classifiers))
    for ax, (label, clf) in graph_data:
        y_pred = clf.predict(X)

        Utils.plot_confusion_matrix(y, y_pred, unique_labels(y), label, ax)
    # plt.title("x")
    plt.show()

    # plot ROC curve and calculate AUC
    for label, clf in classifiers:
        y_pred = clf.predict(X)
        fpr, tpr, thresholds = roc_curve(y, y_pred)
        roc_auc = auc(fpr, tpr)
        plt.plot(
            fpr, tpr, lw=1, alpha=0.3, label="ROC %s (AUC = %0.2f)" % (label, roc_auc)
        )
        plt.plot(
            [0, 1], [0, 1], linestyle="--", lw=2, color="r", label="_Chance", alpha=0.8
        )
    plt.title("Receiver Operating Characteristics")
    plt.legend()
    plt.show()


def do_report(classifiers: List[Tuple[str, Any]], X, y):
    """
    Print key matrics for a set of test data.

    :param classifiers: list of label, classifier tuples
    :param X: a matrix of test samples
    :param y: a vector of categories
    """
    logger.info("Samples: len(X, y) = %d, %d" % (len(X), len(y)))
    unique, counts = np.unique(np.array(y), return_counts=True)
    logger.info("Categories: " + str(list(zip(unique, counts))))

    for label, clf in classifiers:
        _dump_metrics(label, clf, X, y)


def do_learning_curve(classifiers: List[Tuple[str, Any]], X, y):
    """
    Plot learning curves for varying sample sizes.

    :param classifiers: list of label, classifier tuples
    :param X: a matrix of samples. Note this is both training data and test data.
    :param y: a vector of categories
    """
    fig, ax = plt.subplots()
    for label, clf in tqdm(classifiers, desc="Calculating learning curves"):
        train_sizes = np.linspace(0.05, 1, 50)
        train_sizes, train_scores, test_scores = learning_curve(
            clf, X, y, train_sizes=train_sizes, cv=5
        )

        # calculate the average across CV cycle results
        train_mean = np.mean(train_scores, axis=1)
        # train_std = np.std(train_scores, axis=1)
        test_mean = np.mean(test_scores, axis=1)
        test_std = np.std(test_scores, axis=1)

        ax.plot(train_sizes, train_mean, marker="o")  # no label
        ax.plot(train_sizes, test_mean, marker="x", label=label)
        # plt.fill_between(train_sizes, train_mean - train_std, train_mean + train_std, color="#DDDDDD")
        plt.fill_between(
            train_sizes, test_mean - test_std, test_mean + test_std, color="#DDDDDD"
        )

    ax.set_xlabel("Training samples")
    ax.set_ylabel("Score")
    ax.set_title("Learning curve for classifiers")
    ax.legend()
    plt.show()


def _dump_metrics(label, clf, X, y):
    print("-----------------\nSUMMARY FOR CLASSIFIER: %s" % label)
    y_pred = clf.predict(X)
    print("Metrics:\n" + Utils.get_classification_metrics(y, y_pred))
    print("Confusion matrix:")
    print(Utils.get_confusion_matrix(y, y_pred))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Builds scikit-learn/nltk classifiers based on training data."
    )
    parser.add_argument(
        "--features", action="store_true", default=False, help="list features and exit"
    )
    parser.add_argument(
        "--report",
        action="store_true",
        default=False,
        help="print classifier/sub-classifier metrics and exit",
    )
    parser.add_argument(
        "--graphs",
        action="store_true",
        default=False,
        help="print classifier graphs and exit",
    )
    parser.add_argument(
        "--learning",
        action="store_true",
        default=False,
        help="print classifier learning curves",
    )
    args = parser.parse_args()

    data = MovieReviews(3000)

    if args.features:
        print("Features:")
        features = data.features
        for i, feat in enumerate(features):
            print("%d - %s" % (i, feat))
        sys.exit(0)

    sentiment = Sentiment("voting.yaml")

    logger.info("Loading feature sets and training data...")
    X, y = data.get_samples()

    # TODO split data into k-fold samples
    X_train = X[:1900]
    y_train = y[:1900]
    X_test = X[1900:]
    y_test = y[1900:]

    if args.report:
        classifiers = [("voting", sentiment.voting_classifier)] + list(
            sentiment.voting_classifier.sub_classifiers.items()
        )
        do_report(classifiers, X_test, y_test)
        sys.exit(0)

    if args.graphs:
        do_graphs(
            [("voting", sentiment.voting_classifier)]
            + list(sentiment.voting_classifier.sub_classifiers.items()),
            X_test,
            y_test,
        )
        sys.exit(0)

    if args.learning:
        classifiers = list(sentiment.voting_classifier.sub_classifiers.items())
        do_learning_curve(classifiers, X, y)
        sys.exit(0)

    # building classifiers is time-consuming so only do this if we get here
    logger.info("Creating classifiers...")
    sentiment.init_classifiers(X_train, y_train)
    logger.info("Done.")
