#!/usr/bin/env fbpython
# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import unittest

from typing import cast, Dict, List
from ..analyze_leaks import (
    LeakAnalysisResult,
    LeakAnalysisScriptError,
    CallGraph,
    DependencyGraph,
    DynamicCallGraphInputFormat,
    Entrypoints,
    JSON,
    PyreCallGraphInputFormat,
    PysaCallGraphInputFormat,
)


class AnalyzeIssueTraceTest(unittest.TestCase):
    def test_load_pysa_call_graph_input_format(self) -> None:
        json_call_graph: JSON = {
            "my_module.my_function": [
                "something_that.my_function_calls",
                "builtins.print",
                "my_module.my_function",
            ],
            "something_that.my_function_calls": ["int.__str__"],
        }

        call_graph = PysaCallGraphInputFormat(json_call_graph)
        result = call_graph.call_graph

        self.assertEqual(len(result), 2)
        self.assertSetEqual(result["something_that.my_function_calls"], {"int.__str__"})
        self.assertSetEqual(
            result["my_module.my_function"],
            {"something_that.my_function_calls", "builtins.print"},
        )

    def test_load_pyre_call_graph_input_format(self) -> None:
        json_call_graph: JSON = {
            "my_module.my_function": [
                {
                    "keys_we_dont_need": [1, 2, 3],
                    "target": "something_that.my_function_calls",
                },
                {"target": "builtins.print"},
                {"direct_target": "my_module.my_function"},
            ],
            "something_that.my_function_calls": [{"direct_target": "int.__str__"}],
        }

        call_graph = PyreCallGraphInputFormat(json_call_graph)
        result = call_graph.call_graph

        self.assertEqual(len(result), 2)
        self.assertSetEqual(result["something_that.my_function_calls"], {"int.__str__"})
        self.assertSetEqual(
            result["my_module.my_function"],
            {"something_that.my_function_calls", "builtins.print"},
        )

    def test_load_pyre_call_graph_input_format_with_response(self) -> None:
        json_call_graph: JSON = {
            "response": {
                "my_module.my_function": [
                    {
                        "keys_we_dont_need": [1, 2, 3],
                        "target": "something_that.my_function_calls",
                    },
                    {"target": "builtins.print"},
                    {"direct_target": "my_module.my_function"},
                ],
                "something_that.my_function_calls": [{"direct_target": "int.__str__"}],
            }
        }

        call_graph = PyreCallGraphInputFormat(json_call_graph)
        result = call_graph.call_graph

        self.assertEqual(len(result), 2)
        self.assertSetEqual(result["something_that.my_function_calls"], {"int.__str__"})
        self.assertSetEqual(
            result["my_module.my_function"],
            {"something_that.my_function_calls", "builtins.print"},
        )

    def test_load_dynamic_call_graph_input_format(self) -> None:
        json_call_graph: JSON = {
            "my_module:my_function": [
                "something.that:my_module.my_function.calls",
                "something_else.that:my_module.<locals>.my_function.<locals>.calls",
            ],
            "something.that:my_module.my_function.calls": [],
            "something_else.that:my_module.<locals>.my_function.<locals>.calls": [
                "another.function:with.<locals>.in_it"
            ],
            "incorrectly.formatted_qualifier": [
                "incorrectly.formatted_qualifier",
                "another.incorrectly.formatted",
            ],
        }
        call_graph = DynamicCallGraphInputFormat(json_call_graph)
        result = call_graph.call_graph
        expected_call_graph = {
            "my_module.my_function": {
                "something.that.my_module.my_function.calls",
                "something_else.that.my_module.my_function.calls",
            },
            "something.that.my_module.my_function.calls": set(),
            "something_else.that.my_module.my_function.calls": {
                "another.function.with.in_it"
            },
            "incorrectly.formatted_qualifier": {"another.incorrectly.formatted"},
        }
        self.assertEqual(result, expected_call_graph)

    def test_load_call_graph_bad_root(self) -> None:
        call_graph: JSON = ["1234"]

        with self.assertRaises(ValueError):
            PyreCallGraphInputFormat(call_graph)

        with self.assertRaises(ValueError):
            PysaCallGraphInputFormat(call_graph)

    def test_load_call_graph_bad_callers(self) -> None:
        call_graph: JSON = {"caller": 1234}

        with self.assertRaises(ValueError):
            PyreCallGraphInputFormat(call_graph)

        with self.assertRaises(ValueError):
            PysaCallGraphInputFormat(call_graph)

    def test_load_call_graph_bad_callees(self) -> None:
        call_graph: JSON = {"caller": [1, 2, 3]}

        with self.assertRaises(ValueError):
            PyreCallGraphInputFormat(call_graph)

        with self.assertRaises(ValueError):
            PysaCallGraphInputFormat(call_graph)

    def test_load_call_graph_bad_callees_dict_keys(self) -> None:
        call_graph: JSON = {"caller": {"callee": 123}}

        with self.assertRaises(ValueError):
            PyreCallGraphInputFormat(call_graph)

        with self.assertRaises(ValueError):
            PysaCallGraphInputFormat(call_graph)

    def test_load_call_graph_bad_callees_dict_target(self) -> None:
        call_graph: JSON = {"caller": {"target": 123}}

        with self.assertRaises(ValueError):
            PyreCallGraphInputFormat(call_graph)

        with self.assertRaises(ValueError):
            PysaCallGraphInputFormat(call_graph)

    def test_load_call_graph_bad_callees_dict_direct_target(self) -> None:
        call_graph: JSON = {"caller": {"direct_target": 123}}

        with self.assertRaises(ValueError):
            PyreCallGraphInputFormat(call_graph)

        with self.assertRaises(ValueError):
            PysaCallGraphInputFormat(call_graph)

    def test_create_dependency_graph(self) -> None:
        call_graph_json: JSON = {
            "parent.function.one": [
                "child_function.one",
                "child_function.two",
                "child_function.three",
            ],
            "parent.function.two": [
                "child_function.one",
                "child_function.two",
            ],
            "child_function.one": ["child_function.two"],
        }

        input_format = PysaCallGraphInputFormat(call_graph_json)

        expected_dependency_graph = {
            "child_function.one": {
                "parent.function.one",
                "parent.function.two",
            },
            "child_function.two": {
                "parent.function.one",
                "parent.function.two",
                "child_function.one",
            },
            "child_function.three": {
                "parent.function.one",
            },
        }

        actual_dependency_graph = DependencyGraph(input_format, Entrypoints([], set()))

        self.assertSetEqual(
            set(actual_dependency_graph.dependency_graph),
            set(expected_dependency_graph),
        )
        for callee, expected_callers in expected_dependency_graph.items():
            with self.subTest(f"Callee: {callee}"):
                actual_callers = actual_dependency_graph.dependency_graph[callee]

                self.assertSetEqual(actual_callers, expected_callers)

    def test_find_trace_to_parent_simple_path(self) -> None:
        input_format = PysaCallGraphInputFormat(
            {
                "function.start": ["function.one"],
                "function.one": ["function.two", "unrelated.call"],
                "function.two": ["function.three"],
                "function.three": ["print"],
                "unrelated.call": ["int"],
            },
        )
        entrypoints = Entrypoints(["function.start"], input_format.get_keys())
        dependency_graph = DependencyGraph(input_format, entrypoints)

        trace = dependency_graph.find_shortest_trace_to_entrypoint("print")

        self.assertIsNotNone(trace)
        self.assertListEqual(
            trace,
            [
                "print",
                "function.three",
                "function.two",
                "function.one",
                "function.start",
            ],
        )

    def test_find_trace_to_parent_no_path(self) -> None:
        input_format = PysaCallGraphInputFormat(
            {
                "function.start": ["function.one"],
                "function.one": ["function.two"],
                "function.two": ["function.three"],
                "function.three": ["print"],
            },
        )
        entrypoints = Entrypoints(["function.one"], input_format.get_keys())
        dependency_graph = DependencyGraph(input_format, entrypoints)

        trace = dependency_graph.find_shortest_trace_to_entrypoint(
            "this_function_does_not_exist",
        )

        self.assertIsNotNone(trace)
        self.assertListEqual(trace, [])

    def test_find_trace_to_parent_multi_path(self) -> None:
        input_format = PysaCallGraphInputFormat(
            {
                "function.start": ["function.one"],
                "function.one": ["function.two_a", "function.two_b"],
                "function.two_a": ["function.three"],
                "function.two_b": ["function.two_b.extra_call"],
                "function.two_b.extra_call": ["function.three"],
                "function.three": ["print"],
            },
        )
        entrypoints = Entrypoints(["function.start"], input_format.get_keys())
        dependency_graph = DependencyGraph(input_format, entrypoints)

        trace = dependency_graph.find_shortest_trace_to_entrypoint("print")

        self.assertIsNotNone(trace)
        self.assertListEqual(
            trace,
            [
                "print",
                "function.three",
                "function.two_a",
                "function.one",
                "function.start",
            ],
        )

    def test_find_trace_to_parent_incomplete_call_graph(self) -> None:
        # this function tests a call graph whose keys are not fully represented
        # in values and vice-versa
        input_format = PysaCallGraphInputFormat(
            {
                "function.start": ["function.one"],
                "function.one": ["function.two", "unrelated.call_1"],
                "function.two": ["function.three"],
                "function.three": ["print"],
                "unrelated.call_2": ["int"],
            },
        )
        entrypoints = Entrypoints(["function.start"], input_format.get_keys())
        dependency_graph = DependencyGraph(input_format, entrypoints)

        trace = dependency_graph.find_shortest_trace_to_entrypoint("print")

        self.assertIsNotNone(trace)
        self.assertListEqual(
            trace,
            [
                "print",
                "function.three",
                "function.two",
                "function.one",
                "function.start",
            ],
        )

    def test_find_trace_to_parent_cycle_from_bottom(self) -> None:
        input_format = PysaCallGraphInputFormat(
            {
                "function.start": ["function.one"],
                "function.one": ["function.two", "unrelated.call_1"],
                "function.two": ["function.three"],
                "function.three": ["function.one", "print"],
                "unrelated.call_2": ["int"],
            },
        )
        entrypoints = Entrypoints(["function.start"], input_format.get_keys())
        dependency_graph = DependencyGraph(input_format, entrypoints)

        trace = dependency_graph.find_shortest_trace_to_entrypoint("print")

        self.assertIsNotNone(trace)
        self.assertListEqual(
            trace,
            [
                "print",
                "function.three",
                "function.two",
                "function.one",
                "function.start",
            ],
        )

    def test_find_trace_to_parent_cycle_from_top(self) -> None:
        input_format = PysaCallGraphInputFormat(
            {
                "function.start": ["function.one"],
                "function.one": ["function.two", "unrelated.call_1"],
                "function.two": ["function.three"],
                "function.three": ["function.one", "print"],
                "unrelated.call_2": ["int"],
            },
        )
        entrypoints = Entrypoints(["function.start"], input_format.get_keys())
        dependency_graph = DependencyGraph(input_format, entrypoints)

        trace = dependency_graph.find_shortest_trace_to_entrypoint("function.one")

        self.assertIsNotNone(trace)
        self.assertListEqual(
            trace,
            ["function.one", "function.start"],
        )

    def test_find_trace_to_parent_self_call(self) -> None:
        input_format = PysaCallGraphInputFormat(
            {
                "function.start": ["function.one"],
                "function.one": ["function.one", "function.two"],
                "function.two": ["print"],
            },
        )
        entrypoints = Entrypoints(["function.start"], input_format.get_keys())
        dependency_graph = DependencyGraph(input_format, entrypoints)

        trace = dependency_graph.find_shortest_trace_to_entrypoint("print")

        self.assertIsNotNone(trace)
        self.assertListEqual(
            trace,
            ["print", "function.two", "function.one", "function.start"],
        )

    def test_find_trace_to_parent_start_is_entrypoint(self) -> None:
        input_format = PysaCallGraphInputFormat(
            {
                "function.start": ["function.start"],
            },
        )
        entrypoints = Entrypoints(["function.start"], input_format.get_keys())
        dependency_graph = DependencyGraph(input_format, entrypoints)

        trace = dependency_graph.find_shortest_trace_to_entrypoint("function.start")

        self.assertIsNotNone(trace)
        self.assertListEqual(
            trace,
            ["function.start"],
        )

    def test_find_trace_to_parent_multiple_valid_entrypoints(self) -> None:
        input_format = PysaCallGraphInputFormat(
            {
                "function.start": ["function.one"],
                "function.one": ["function.two", "unrelated.call_1"],
                "function.two": ["function.three"],
                "function.three": ["function.one", "print"],
                "unrelated.call_2": ["int"],
            },
        )
        entrypoints = Entrypoints(
            ["function.start", "function.one"], input_format.get_keys()
        )
        dependency_graph = DependencyGraph(
            input_format,
            entrypoints,
        )

        trace = dependency_graph.find_shortest_trace_to_entrypoint("print")

        self.assertIsNotNone(trace)
        self.assertListEqual(
            trace,
            ["print", "function.three", "function.two", "function.one"],
        )

    def test_validate_entrypoints_file_happy_path(self) -> None:
        entrypoints_list: JSON = ["my.entrypoint.one", "doesnt.exist"]
        input_format = PysaCallGraphInputFormat({"my.entrypoint.one": ["print"]})
        entrypoints = Entrypoints(entrypoints_list, input_format.get_keys())

        self.assertSetEqual(entrypoints.entrypoints, {"my.entrypoint.one"})

    def test_validate_entrypoints_file_bad_root(self) -> None:
        entrypoints_list: JSON = {"not_a_list": True}

        with self.assertRaises(ValueError):
            input_format = PysaCallGraphInputFormat({"my.entrypoint.one": ["print"]})
            Entrypoints(entrypoints_list, input_format.get_keys())

    def test_validate_entrypoints_file_bad_list_elements(self) -> None:
        entrypoints_list: JSON = [True, 1]

        with self.assertRaises(ValueError):
            input_format = PysaCallGraphInputFormat({"my.entrypoint.one": ["print"]})
            Entrypoints(entrypoints_list, input_format.get_keys())

    def test_get_transitive_callees_empty(self) -> None:
        entrypoints_list: JSON = []
        input_format = PysaCallGraphInputFormat({"f1": ["f2", "f3"], "f2": ["f1"]})
        entrypoints = Entrypoints(entrypoints_list, input_format.get_keys())
        call_graph = CallGraph(input_format, entrypoints)

        callees = call_graph.get_transitive_callees_and_traces()

        self.assertEqual(callees, {})

    def test_get_transitive_callees_f1(self) -> None:
        entrypoints_list: JSON = ["f1"]
        input_format = PysaCallGraphInputFormat(
            {"f1": ["f2", "f3"], "f2": ["f1"], "f3": ["f3"]}
        )
        entrypoints = Entrypoints(entrypoints_list, input_format.get_keys())
        call_graph = CallGraph(input_format, entrypoints)

        callees = call_graph.get_transitive_callees_and_traces()

        self.assertEqual(
            callees, {"f1": ["f1"], "f2": ["f1", "f2"], "f3": ["f1", "f3"]}
        )

    def test_get_transitive_callees_f2(self) -> None:
        entrypoints_list: JSON = ["f2"]
        input_format = PysaCallGraphInputFormat(
            {"f1": ["f2", "f3"], "f2": ["f1"], "f3": ["f3"]}
        )
        entrypoints = Entrypoints(entrypoints_list, input_format.get_keys())
        call_graph = CallGraph(input_format, entrypoints)

        callees = call_graph.get_transitive_callees_and_traces()

        self.assertEqual(
            callees, {"f1": ["f2", "f1"], "f2": ["f2"], "f3": ["f2", "f1", "f3"]}
        )

    def test_get_transitive_callees_f3(self) -> None:
        entrypoints_list: JSON = ["f3"]
        input_format = PysaCallGraphInputFormat(
            {"f1": ["f2", "f3"], "f2": ["f1"], "f3": ["f3"]}
        )
        entrypoints = Entrypoints(entrypoints_list, input_format.get_keys())
        call_graph = CallGraph(input_format, entrypoints)

        callees = call_graph.get_transitive_callees_and_traces()

        self.assertEqual(callees, {"f3": ["f3"]})

    def test_get_transitive_callees_multiple(self) -> None:
        entrypoints_list: JSON = ["f1", "f4"]
        input_format = PysaCallGraphInputFormat(
            {
                "f1": ["f2", "f3"],
                "f2": ["f1"],
                "f3": ["f3"],
                "f4": ["f5"],
                "f5": ["print"],
                "f6": [],
            },
        )
        entrypoints = Entrypoints(entrypoints_list, input_format.get_keys())
        call_graph = CallGraph(
            input_format,
            entrypoints,
        )

        callees = call_graph.get_transitive_callees_and_traces()

        self.assertEqual(
            callees,
            {
                "f1": ["f1"],
                "f2": ["f1", "f2"],
                "f3": ["f1", "f3"],
                "f4": ["f4"],
                "f5": ["f4", "f5"],
                "print": ["f4", "f5", "print"],
            },
        )

    def test_is_valid_callee(self) -> None:
        self.assertTrue(CallGraph.is_valid_callee("f1"))
        self.assertTrue(CallGraph.is_valid_callee("f1.f2.f3"))
        self.assertFalse(CallGraph.is_valid_callee("11"))
        self.assertFalse(CallGraph.is_valid_callee("-f1.f2"))
        self.assertFalse(CallGraph.is_valid_callee("f1#f2"))


    def test_prepare_issues_for_query(self) -> None:
        callees = ["f1", "f2", "f3", "f1#f2", "f1.f2.f3", "11", "-f1.f2"]

        result_query = CallGraph.prepare_issues_for_query(callees)
        expected_query = "batch(global_leaks(f1), global_leaks(f2), global_leaks(f3), global_leaks(f1.f2.f3))"

        self.assertEqual(result_query, expected_query)


    def test_collect_pyre_query_results(self) -> None:
        example_pyre_stdout = {
            "response": [
                {"error": "we failed to find your callable"},
                {
                    "response": {
                        "errors": [
                            {
                                "error_msg": "found an error for you",
                                "location": "your_location",
                            }
                        ]
                    }
                },
                {"error": "we failed to find your callable 2"},
                {
                    "response": {
                        "errors": [
                            {
                                "error_msg": "found an error for you2",
                                "location": "your_location2",
                                "define": "my_func_with_trace",
                            }
                        ]
                    }
                },
                ["not_expected"],
                {"not_expected": 1},
            ]
        }

        results = CallGraph.collect_pyre_query_results(
            example_pyre_stdout,
        )
        expected_results = LeakAnalysisResult(
            global_leaks=[
                {
                    "error_msg": "found an error for you",
                    "location": "your_location",
                },
                {
                    "error_msg": "found an error for you2",
                    "location": "your_location2",
                    "define": "my_func_with_trace",
                },
            ],
            query_errors=[
                "we failed to find your callable",
                "we failed to find your callable 2",
            ],
            script_errors=[
                LeakAnalysisScriptError(
                    error_message="Expected dict for pyre response list type, got <class 'list'>",
                    bad_value=["not_expected"],
                ),
                LeakAnalysisScriptError(
                    error_message="Unexpected single query response from Pyre",
                    bad_value={"not_expected": 1},
                ),
            ],
        )

        self.assertEqual(results, expected_results)

    def test_collect_pyre_query_results_non_json(self) -> None:
        example_pyre_stdout = """
            this is not a valid response
        """

        with self.assertRaises(RuntimeError):
            CallGraph.collect_pyre_query_results(example_pyre_stdout)

    def test_collect_pyre_query_results_not_top_level_dict(self) -> None:
        example_pyre_stdout = """
            ["this is a list"]
        """

        with self.assertRaises(RuntimeError):
            CallGraph.collect_pyre_query_results(example_pyre_stdout)

    def test_collect_pyre_query_results_no_response_present(self) -> None:
        example_pyre_stdout = """
            {"not a response": 1}
        """

        with self.assertRaises(RuntimeError):
            CallGraph.collect_pyre_query_results(example_pyre_stdout)

    def test_collect_pyre_query_results_response_not_a_list(self) -> None:
        example_pyre_stdout = """
            {"response": 1}
        """

        with self.assertRaises(RuntimeError):
            CallGraph.collect_pyre_query_results(example_pyre_stdout)

    def test_collect_pyre_query_results_response_batch_response_not_a_dict(
        self,
    ) -> None:
        example_pyre_stdout = """
            {
                "response": [
                    123
                ]
            }
        """

        with self.assertRaises(RuntimeError):
            CallGraph.collect_pyre_query_results(example_pyre_stdout)

    def test_collect_pyre_query_results_response_batch_response_no_nested_error_or_response(
        self,
    ) -> None:
        example_pyre_stdout = """
            {
                "response": {
                    "not_error": 123,
                    "not_response": 456
                }
            }
        """

        with self.assertRaises(RuntimeError):
            CallGraph.collect_pyre_query_results(example_pyre_stdout)

    def test_attach_trace_to_query_results(self) -> None:
        pyre_results = LeakAnalysisResult(
            global_leaks=[
                {
                    "error_msg": "found an error for you",
                    "location": "your_location",
                },
                {
                    "error_msg": "found an error for you2",
                    "location": "your_location2",
                    "define": "my_func_with_trace",
                },
                {
                    "error_msg": "found an error for you3",
                    "location": "your_location3",
                    "define": "my_func_without_trace",
                },
            ],
            query_errors=[
                {"errors": "we failed to find your callable"},
                {"errors": "we failed to find your callable 2"},
            ],
            script_errors=[],
        )
        expected = LeakAnalysisResult(
            global_leaks=cast(
                List[Dict[str, JSON]],
                [
                    {
                        "error_msg": "found an error for you",
                        "location": "your_location",
                    },
                    {
                        "error_msg": "found an error for you2",
                        "location": "your_location2",
                        "define": "my_func_with_trace",
                        "trace": ["func_1", "my_func_with_trace"],
                    },
                    {
                        "error_msg": "found an error for you3",
                        "location": "your_location3",
                        "define": "my_func_without_trace",
                    },
                ],
            ),
            query_errors=[
                {"errors": "we failed to find your callable"},
                {"errors": "we failed to find your callable 2"},
            ],
            script_errors=[
                LeakAnalysisScriptError(
                    error_message="Key `define` not present in global leak result, skipping trace",
                    bad_value={
                        "error_msg": "found an error for you",
                        "location": "your_location",
                    },
                ),
                LeakAnalysisScriptError(
                    error_message="Define not known in analyzed callables, skipping trace",
                    bad_value={
                        "error_msg": "found an error for you3",
                        "location": "your_location3",
                        "define": "my_func_without_trace",
                    },
                ),
            ],
        )
        callables_and_traces = {
            "my_func_with_trace": ["func_1", "my_func_with_trace"],
        }

        self.assertNotEqual(pyre_results, expected)
        CallGraph.attach_trace_to_query_results(pyre_results, callables_and_traces)
        print(pyre_results)
        print(expected)
        self.assertEqual(pyre_results, expected)

    def assert_format_qualifier(self, input: str, expected: str) -> None:
        self.assertEqual(DynamicCallGraphInputFormat.format_qualifier(input), expected)

    def test_dynamic_call_graph_input_format_format_qualifier_1(self) -> None:
        self.assert_format_qualifier(
            "this_is.a_normal_qualifier",
            "this_is.a_normal_qualifier",
        )

    def test_dynamic_call_graph_input_format_format_qualifier_2(self) -> None:
        self.assert_format_qualifier(
            "this.is_a.qualifier:with.an_included.path",
            "this.is_a.qualifier.with.an_included.path",
        )

    def test_dynamic_call_graph_input_format_format_qualifier_3(self) -> None:
        self.assert_format_qualifier(
            "this_qualifier_is_probably_broken_but_its_ok",
            "this_qualifier_is_probably_broken_but_its_ok",
        )

    def test_dynamic_call_graph_input_format_format_qualifier_4(self) -> None:
        self.assert_format_qualifier(
            "this_is.<locals>.a_normal_qualifier",
            "this_is.a_normal_qualifier",
        )

    def test_dynamic_call_graph_input_format_format_qualifier_5(self) -> None:
        self.assert_format_qualifier(
            "this.is_a.qualifier:with.<locals>.an_included.path",
            "this.is_a.qualifier.with.an_included.path",
        )

    def test_dynamic_call_graph_input_format_format_qualifier_6(self) -> None:
        self.assert_format_qualifier(
            "this.is:a.<locals>.qualifier.<locals>.with.<locals>.and_included.<locals>.path",
            "this.is.a.qualifier.with.and_included.path",
        )

    def test_dynamic_call_graph_input_format_get_keys_extracts_caller(self) -> None:
        input_format = DynamicCallGraphInputFormat(
            {
                "my_module:my_function": [
                    "something.that:my_module.my_function.calls",
                    "something_else.that:my_module.<locals>.my_function.<locals>.calls",
                ],
                "something.that:my_module.my_function.calls": [],
                "something_else.that:my_module.<locals>.my_function.<locals>.calls": [
                    "another.function:with.<locals>.in_it"
                ],
                "incorrectly.formatted_qualifier": [
                    "incorrectly.formatted_qualifier",
                    "another.incorrectly.formatted",
                ],
            }
        )

        expected = {
            "my_module.my_function",
            "something.that.my_module.my_function.calls",
            "something_else.that.my_module.my_function.calls",
            "incorrectly.formatted_qualifier",
        }

        self.assertEqual(input_format.get_keys(), expected)
