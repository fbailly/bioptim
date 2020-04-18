import multiprocessing as mp
import numpy as np
import tkinter

from matplotlib import pyplot as plt
from casadi import Callback, nlpsol_out, nlpsol_n_out, Sparsity
import numpy as np

from .problem_type import ProblemType

height = 2.4
muscle_position = 1000
width_step = 4
width_max = 10


class PlotOcp:
    def __init__(self, ocp):

        self.ocp = ocp
        self.ns_per_phase = [nlp["ns"] + 1 for nlp in ocp.nlp]
        self.ydata = []
        self.ns = 0

        self.problem_type = None
        for i, nlp in enumerate(self.ocp.nlp):
            if self.problem_type is None:
                self.problem_type = nlp["problem_type"]

            if i == 0:
                self.t = np.linspace(0, nlp["tf"], nlp["ns"] + 1)
            else:
                self.t = np.append(self.t, np.linspace(self.t[-1], self.t[-1] + nlp["tf"], nlp["ns"] + 1),)
            self.ns += nlp["ns"] + 1

        self.axes = []
        if (
            self.problem_type == ProblemType.torque_driven
            or self.problem_type == ProblemType.torque_driven_with_contact
            or self.problem_type == ProblemType.muscles_and_torque_driven
        ):
            for i in range(self.ocp.nb_phases):
                if self.ocp.nlp[0]["nbQ"] != self.ocp.nlp[i]["nbQ"]:
                    raise RuntimeError("Graphs with nbQ different at each phase is not implemented yet")
            nlp = self.ocp.nlp[0]

            self.all_figures = []
            for j, type in enumerate(["Q", "Qdot", "Tau"]):
                self.all_figures.append(
                    plt.figure(type, figsize=(min(nlp["nb" + type] * width_step, width_max), height))
                )
                axes_dof = self.all_figures[-1].subplots(1, nlp["nb" + type]).flatten()
                self.axes.extend(axes_dof)
                mid_column_idx = int(nlp["nb" + type] / 2)
                axes_dof[mid_column_idx].set_title(type)
                axes_dof[nlp["nb" + type] - mid_column_idx].set_xlabel("time (s)")
                self.all_figures[-1].tight_layout()

            if self.problem_type == ProblemType.muscles_and_torque_driven:

                nlp = self.ocp.nlp[0]
                nb_cols = int(np.sqrt(nlp["nbMuscle"])) + 1
                if nb_cols * (nb_cols - 1) >= nlp["nbMuscle"]:
                    nb_rows = nb_cols - 1
                else:
                    nb_rows = nb_cols

                self.all_figures.append(
                    plt.figure("Muscles", figsize=(min(nb_cols * width_step, width_max), min(nb_rows, 4) * height))
                )
                axes_muscles = self.all_figures[-1].subplots(nb_rows, nb_cols).flatten()
                self.axes.extend(axes_muscles)
                for k in range(nlp["nbMuscle"]):
                    axes_muscles[k].set_title(nlp["model"].muscleNames()[k].to_string())
                axes_muscles[nb_rows * nb_cols - int(nb_cols / 2) - 1].set_xlabel("time (s)")
                self.all_figures[-1].tight_layout()

            intersections_time = PlotOcp.find_phases_intersections(ocp)
            for i, ax in enumerate(self.axes):
                if i < self.ocp.nlp[0]["nx"]:
                    ax.plot(self.t, np.zeros((self.ns, 1)))
                elif i < self.ocp.nlp[0]["nx"] + self.ocp.nlp[0]["nbTau"]:
                    ax.step(self.t, np.zeros((self.ns, 1)), where="post")
                else:
                    ax.step(self.t, np.zeros((self.ns, 1)), where="post")

                for time in intersections_time:
                    ax.axvline(time, linestyle="--", linewidth=1.2, c="k")
                ax.grid(color="k", linestyle="--", linewidth=0.5)
                ax.set_xlim(0, self.t[-1])

        else:
            raise RuntimeError("Plot is not ready for this type of OCP")

    @staticmethod
    def find_phases_intersections(ocp):
        intersections_time = []
        time = 0
        for i in range(len(ocp.nlp) - 1):
            time += ocp.nlp[i]["tf"]
            intersections_time.append(time)
        return intersections_time

    @staticmethod
    def show():
        plt.show()

    def update_data(self, V):
        self.ydata = [[] for _ in range(self.ocp.nb_phases)]
        for i, nlp in enumerate(self.ocp.nlp):
            if (
                self.problem_type == ProblemType.torque_driven
                or self.problem_type == ProblemType.torque_driven_with_contact
                or self.problem_type == ProblemType.muscles_and_torque_driven
            ):
                if (
                    self.problem_type == ProblemType.torque_driven
                    or self.problem_type == ProblemType.torque_driven_with_contact
                ):
                    # TODO: Add an integrator for the states
                    q, q_dot, tau = ProblemType.get_data_from_V(self.ocp, V, i)
                    self.__update_ydata(q, nlp["nbQ"], i)
                    self.__update_ydata(q_dot, nlp["nbQdot"], i)
                    self.__update_ydata(tau, nlp["nbTau"], i)

                elif self.problem_type == ProblemType.muscles_and_torque_driven:
                    q, q_dot, tau, muscle = ProblemType.get_data_from_V(self.ocp, V, i)
                    self.__update_ydata(q, nlp["nbQ"], i)
                    self.__update_ydata(q_dot, nlp["nbQdot"], i)
                    self.__update_ydata(tau, nlp["nbTau"], i)
                    self.__update_ydata(muscle, nlp["nbMuscle"], i)

        self.__update_axes()

    def __update_ydata(self, array, nb_variables, phase_idx):
        for i in range(nb_variables):
            self.ydata[phase_idx].append(array[i, :])

    def __update_axes(self):
        for i, ax in enumerate(self.axes):
            y = np.array([])
            for phase in self.ydata:
                y = np.append(y, phase[i])

            y_range = np.max([np.max(y) - np.min(y), 0.5])
            mean = y_range / 2 + np.min(y)
            axe_range = (1.1 * y_range) / 2
            ax.set_ylim(mean - axe_range, mean + axe_range)
            ax.set_yticks(
                np.arange(
                    np.round(mean - axe_range, 1),
                    np.round(mean + axe_range, 1),
                    step=np.round((mean + axe_range - (mean - axe_range)) / 4, 1),
                )
            )
            ax.get_lines()[0].set_ydata(y)


class AnimateCallback(Callback):
    def __init__(self, ocp, opts={}):
        Callback.__init__(self)
        self.nlp = ocp
        self.nx = ocp.V.rows()
        self.ng = ocp.g.rows()
        self.construct("AnimateCallback", opts)

        self.plot_pipe, plotter_pipe = mp.Pipe()
        self.plotter = self.ProcessPlotter(ocp)
        self.plot_process = mp.Process(target=self.plotter, args=(plotter_pipe,), daemon=True)
        self.plot_process.start()

    @staticmethod
    def get_n_in():
        return nlpsol_n_out()

    @staticmethod
    def get_n_out():
        return 1

    @staticmethod
    def get_name_in(i):
        return nlpsol_out(i)

    @staticmethod
    def get_name_out(_):
        return "ret"

    def get_sparsity_in(self, i):
        n = nlpsol_out(i)
        if n == "f":
            return Sparsity.scalar()
        elif n in ("x", "lam_x"):
            return Sparsity.dense(self.nx)
        elif n in ("g", "lam_g"):
            return Sparsity.dense(self.ng)
        else:
            return Sparsity(0, 0)

    def eval(self, arg):
        send = self.plot_pipe.send
        send(arg[0])
        return [0]

    class ProcessPlotter(object):
        def __init__(self, ocp):
            self.ocp = ocp

        def __call__(self, pipe):
            self.pipe = pipe
            self.plot = PlotOcp(self.ocp)
            timer = self.plot.all_figures[0].canvas.new_timer(interval=100)
            timer.add_callback(self.callback)
            timer.start()

            plt.show()

        def callback(self):
            while self.pipe.poll():
                V = self.pipe.recv()
                self.plot.update_data(V)

            if self.ocp.nlp[0]["problem_type"] == ProblemType.torque_driven:
                height_step = int(tkinter.Tk().winfo_screenheight() / len(self.plot.all_figures))
            if self.ocp.nlp[0]["problem_type"] == ProblemType.muscles_and_torque_driven:
                height_step = int(tkinter.Tk().winfo_screenheight() / (len(self.plot.all_figures) - 1))

            for i, fig in enumerate(self.plot.all_figures):
                if (
                    self.ocp.nlp[0]["problem_type"] == ProblemType.muscles_and_torque_driven
                    and fig == self.plot.all_figures[-1]
                ):
                    fig.canvas.manager.window.move(muscle_position, 0)

                elif (
                    self.ocp.nlp[0]["problem_type"] == ProblemType.torque_driven
                    or self.ocp.nlp[0]["problem_type"] == ProblemType.muscles_and_torque_driven
                ):
                    fig.canvas.manager.window.move(20, i * height_step)

                fig.canvas.draw()
            return True
